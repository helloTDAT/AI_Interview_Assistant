from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from app.core.storage import store
from app.models import (
    LearningAnswerFeedback,
    LearningInsightNode,
    Question,
    QuestionSource,
    ResumeProfile,
)
from app.services.ai_clients import LLMClient
from app.services.learning_rag import LearningRagService


PASSING_SCORE = 60


class QuestionGenerationAgent:
    def __init__(self, llm: LLMClient | None = None, rag: LearningRagService | None = None) -> None:
        self.llm = llm or LLMClient()
        self.rag = rag or LearningRagService(self.llm)

    def generate_for_resume(
        self,
        profile: ResumeProfile | dict | None,
        target_position: str = "后端开发工程师",
        count: int = 5,
    ) -> list[Question]:
        return self.feed("demo-user", profile, target_position, count)["questions"]

    def feed(
        self,
        user_id: str,
        profile: ResumeProfile | dict | None,
        target_position: str,
        limit: int = 8,
        last_answer_score: int | None = None,
    ) -> dict[str, Any]:
        skills = self._skills(profile, target_position)
        desired_difficulty = self._next_difficulty(last_answer_score)
        self._maybe_generate_questions(target_position, skills, desired_difficulty, max(0, limit - 3))
        questions = sorted(
            store.questions.values(),
            key=lambda question: self._rank(question, target_position, skills, desired_difficulty),
            reverse=True,
        )
        selected = questions[: max(1, min(limit, 20))]
        return {
            "questions": selected,
            "insights": self.insights(user_id, skills),
            "rag_status": {
                "chunks": len(store.rag_chunks),
                "provider": "chatanywhere",
                "fallback_ready": True,
            },
        }

    def answer(self, payload) -> LearningAnswerFeedback:
        question = store.questions.get(payload.question_id)
        if not question:
            raise KeyError("question not found")
        answer_text = payload.answer_text.strip()
        contexts = self.rag.search(
            f"{question.title}\n{answer_text}",
            top_k=4,
            skill_tags=question.skill_tags,
        )
        llm_result = self.llm.evaluate_learning_answer(question, answer_text, [chunk.text for chunk in contexts])
        if llm_result.ok and llm_result.data:
            feedback = self._feedback_from_llm(question.id, llm_result.data)
        else:
            feedback = self._rule_feedback(question, answer_text)
            feedback.source = "rules_fallback" if llm_result.error != "chatanywhere api key is not configured" else "rules"
        store.learning_answers.setdefault(payload.user_id, []).append(feedback)
        return feedback

    def mistakes(self, user_id: str) -> list[dict[str, Any]]:
        records = store.learning_answers.get(user_id, [])
        low_scores = [record for record in records if not record.passed]
        return [
            {
                "feedback": record.model_dump(mode="json"),
                "question": store.questions.get(record.question_id).model_dump(mode="json")
                if store.questions.get(record.question_id)
                else None,
            }
            for record in low_scores
        ]

    def insights(self, user_id: str, skills: list[str] | None = None) -> list[LearningInsightNode]:
        attempts_by_skill: dict[str, list[int]] = defaultdict(list)
        for record in store.learning_answers.get(user_id, []):
            question = store.questions.get(record.question_id)
            if not question:
                continue
            for skill in question.skill_tags or ["综合表达"]:
                attempts_by_skill[skill].append(record.score)

        baseline = skills or ["项目经历", "数据库", "表达能力"]
        nodes: list[LearningInsightNode] = []
        for skill in dict.fromkeys([*baseline, *attempts_by_skill.keys()]):
            scores = attempts_by_skill.get(skill, [])
            mastery = round(sum(scores) / len(scores)) if scores else 20
            if mastery >= 80:
                status = "lit"
            elif scores:
                status = "warming"
            else:
                status = "locked"
            nodes.append(LearningInsightNode(skill=skill, mastery=mastery, attempts=len(scores), status=status))
        return nodes[:12]

    def add_real_interview_question(self, title: str, target_position: str | None = None) -> Question:
        normalized = title.strip()
        for question in store.questions.values():
            if question.title == normalized and question.source == QuestionSource.real_interview:
                question.occurrence_count += 1
                question.badge = "高频实战"
                self.rag.add_question(question)
                return question
        question = Question(
            title=normalized,
            answer_reference="来自真实面试录音，建议结合岗位要求补充标准答案与追问点。",
            source=QuestionSource.real_interview,
            position=target_position,
            skill_tags=["真实面试", "项目经历"],
            difficulty="medium",
            occurrence_count=1,
            badge="高频实战",
        )
        store.questions[question.id] = question
        self.rag.add_question(question)
        return question

    def _maybe_generate_questions(self, target_position: str, skills: list[str], difficulty: str, count: int) -> None:
        if count <= 0:
            return
        existing_titles = {question.title for question in store.questions.values()}
        contexts = self.rag.search(f"{target_position} {' '.join(skills)}", top_k=4, skill_tags=skills)
        result = self.llm.generate_learning_questions(
            target_position=target_position,
            skills=skills,
            rag_context=[chunk.text for chunk in contexts],
            count=count,
            difficulty=difficulty,
        )
        if result.ok and result.data and isinstance(result.data.get("questions"), list):
            for item in result.data["questions"][:count]:
                if not isinstance(item, dict) or not item.get("title") or item["title"] in existing_titles:
                    continue
                question = Question(
                    title=str(item["title"]),
                    answer_reference=str(item.get("answer_reference") or "请围绕场景、方案、难点、结果展开回答。"),
                    source=QuestionSource.generated,
                    position=target_position,
                    skill_tags=[str(tag) for tag in item.get("skill_tags", [])][:6] or skills[:2],
                    difficulty=str(item.get("difficulty") or difficulty),
                )
                store.questions[question.id] = question
                self.rag.add_question(question)
            return

        for skill in skills[:count]:
            title = f"请结合你的经历说明你如何使用 {skill} 解决实际问题。"
            if title in existing_titles:
                continue
            question = Question(
                title=title,
                answer_reference="建议说明场景、技术选择、实现步骤、难点处理和结果指标。",
                source=QuestionSource.generated,
                position=target_position,
                skill_tags=[skill],
                difficulty=difficulty,
            )
            store.questions[question.id] = question
            self.rag.add_question(question)

    def _skills(self, profile: ResumeProfile | dict | None, target_position: str) -> list[str]:
        if isinstance(profile, ResumeProfile) and profile.skills:
            return profile.skills
        if isinstance(profile, dict) and profile.get("skills"):
            return [str(skill) for skill in profile.get("skills", [])]
        if "Java" in target_position:
            return ["Java", "Spring Boot", "MySQL", "Redis", "并发"]
        if "AI" in target_position or "算法" in target_position:
            return ["Python", "机器学习", "深度学习", "PyTorch", "SQL"]
        if "数据" in target_position:
            return ["SQL", "Python", "数据分析", "可视化"]
        return ["项目经历", "数据库", "沟通表达"]

    def _next_difficulty(self, last_answer_score: int | None) -> str:
        if last_answer_score is None:
            return "medium"
        if last_answer_score >= 82:
            return "hard"
        if last_answer_score < PASSING_SCORE:
            return "easy"
        return "medium"

    def _rank(self, question: Question, target_position: str, skills: list[str], difficulty: str) -> float:
        score = 0.0
        if question.position and (question.position in target_position or target_position in question.position):
            score += 2.5
        if any(tag in skills for tag in question.skill_tags):
            score += 2.0
        if question.difficulty == difficulty:
            score += 1.2
        if question.source == QuestionSource.real_interview:
            score += 2.0 + min(question.occurrence_count, 5) * 0.2
        elif question.source == QuestionSource.open_source:
            score += 1.0
        elif question.source == QuestionSource.handbook:
            score += 0.7
        return score

    def _feedback_from_llm(self, question_id: str, data: dict[str, Any]) -> LearningAnswerFeedback:
        score = self._clamp(data.get("score", 0))
        return LearningAnswerFeedback(
            question_id=question_id,
            score=score,
            passed=score >= PASSING_SCORE,
            highlights=self._strings(data.get("highlights")) or ["回答已经覆盖了部分关键点。"],
            improvements=self._strings(data.get("improvements")) or ["建议补充场景、取舍、难点和结果。"],
            senior_answer=str(data.get("senior_answer") or "资深工程师会先澄清场景，再说明方案取舍、风险控制和可验证结果。"),
            next_difficulty=self._next_difficulty(score),
            source="llm",
        )

    def _rule_feedback(self, question: Question, answer_text: str) -> LearningAnswerFeedback:
        terms = set(question.skill_tags)
        hit_count = sum(1 for term in terms if term and term.lower() in answer_text.lower())
        length_score = min(45, len(answer_text) // 3)
        structure_score = 20 if any(word in answer_text for word in ["背景", "方案", "结果", "难点", "优化"]) else 8
        score = self._clamp(25 + length_score + structure_score + hit_count * 8)
        improvements = ["补充具体业务场景、个人贡献和量化结果。"]
        if not hit_count and question.skill_tags:
            improvements.append(f"回答中还需要显式覆盖：{', '.join(question.skill_tags[:3])}。")
        return LearningAnswerFeedback(
            question_id=question.id,
            score=score,
            passed=score >= PASSING_SCORE,
            highlights=["回答已经开始围绕题目展开。"] if answer_text else [],
            improvements=improvements,
            senior_answer=question.answer_reference
            or "资深工程师会用 STAR 结构说明背景、行动、技术取舍、风险和结果。",
            next_difficulty=self._next_difficulty(score),
            source="rules",
        )

    def _clamp(self, value: Any) -> int:
        try:
            score = int(round(float(value)))
        except (TypeError, ValueError):
            score = 0
        return max(0, min(100, score))

    def _strings(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()][:5]
