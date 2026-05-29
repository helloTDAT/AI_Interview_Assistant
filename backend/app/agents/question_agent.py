from __future__ import annotations

import re
from collections import defaultdict
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
        contexts = self.rag.search(f"{target_position} {' '.join(skills)}", top_k=4, skill_tags=skills)
        self._maybe_generate_questions(target_position, skills, desired_difficulty, max(0, limit - 3), contexts)
        questions = sorted(
            store.questions.values(),
            key=lambda question: self._rank(question, target_position, skills, desired_difficulty),
            reverse=True,
        )
        selected = self._balanced_selection(questions, skills, max(1, min(limit, 20)))
        return {
            "questions": selected,
            "insights": self.insights(user_id, skills),
            "rag_status": {
                "chunks": len(store.rag_chunks),
                "provider": "local",
                "retrieved": len(contexts),
                "sources": self._rag_sources(contexts),
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
            prompt="请先给出核心结论，再结合真实面试场景说明方案、边界和追问点。",
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

    def _maybe_generate_questions(
        self,
        target_position: str,
        skills: list[str],
        difficulty: str,
        count: int,
        contexts: list[Any] | None = None,
    ) -> None:
        if count <= 0:
            return
        existing_titles = {question.title for question in store.questions.values()}
        generated_count = 0
        local_blueprints = self._local_question_blueprints(skills, target_position, difficulty, contexts or [])
        for title, prompt, tags in local_blueprints:
            if title in existing_titles:
                continue
            question = Question(
                title=title,
                prompt=prompt,
                answer_reference="建议说明核心概念、适用场景、方案取舍、风险边界和可验证结果。",
                source=QuestionSource.generated,
                position=target_position,
                skill_tags=tags,
                difficulty=difficulty,
            )
            store.questions[question.id] = question
            self.rag.add_question(question)
            existing_titles.add(title)
            generated_count += 1
            if generated_count >= count:
                break

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

    def _balanced_selection(self, questions: list[Question], skills: list[str], limit: int) -> list[Question]:
        buckets = [
            ("real", lambda q: q.source == QuestionSource.real_interview),
            ("project", lambda q: any(tag in {"项目经历", "真实面试", "沟通表达"} for tag in q.skill_tags) or "项目" in q.title),
            ("skill", lambda q: any(tag in skills for tag in q.skill_tags)),
            ("foundation", lambda q: any(tag in {"数据库", "MySQL", "Redis", "并发", "HTTP", "JVM", "网络"} for tag in q.skill_tags)),
            ("algorithm", lambda q: any(tag in {"算法", "复杂度", "数据结构"} for tag in q.skill_tags) or "算法" in q.title),
            ("system", lambda q: "系统" in q.title or "设计" in q.title or any(tag == "系统设计" for tag in q.skill_tags)),
        ]
        selected: list[Question] = []
        seen: set[str] = set()
        for _, matcher in buckets:
            for question in questions:
                if question.id not in seen and matcher(question):
                    selected.append(question)
                    seen.add(question.id)
                    break
            if len(selected) >= limit:
                return selected
        for question in questions:
            if question.id in seen:
                continue
            selected.append(question)
            if len(selected) >= limit:
                break
        return selected

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

    def _normalize_question_text(self, raw_title: str, raw_prompt: str = "") -> tuple[str, str]:
        title = self._clean_text(raw_title)
        prompt = self._clean_text(raw_prompt)
        markers = ["要求包含", "请按 STAR", "提示：", "提示:", "回答要点", "要求包括", "请说明", "请描述"]
        should_split = len(title) > 60 or any(marker in title for marker in markers) or title.count("；") >= 2 or title.count("，") >= 4
        if should_split:
            prompt = prompt or title
            title = self._short_title_from_text(title)
        return title[:60].strip(" ，。；;") or "综合面试练习题", self._compact_prompt(prompt)

    def _short_title_from_text(self, text: str) -> str:
        compact = re.sub(r"[\s　]+", "", text)
        patterns = [
            r"(Redis|MySQL|SQL|Netty|RocketMQ|Spring|JVM|HTTP|PyTorch|Python|Java|WebRTC|RAG|Agent)[^，。；;]{0,24}",
            r"(缓存|数据库|接口|并发|索引|事务|算法|系统设计|项目沟通|项目复盘)[^，。；;]{0,24}",
        ]
        for pattern in patterns:
            match = re.search(pattern, compact, flags=re.I)
            if match:
                candidate = match.group(0).strip(" ：:，。；;")
                if 6 <= len(candidate) <= 40:
                    return candidate if candidate.endswith("？") else f"{candidate}怎么处理？"
        first = re.split(r"[。；;\n]", text)[0].strip()
        first = re.sub(r"^(请|面试官可能会追问：?|请按STAR结构，?)", "", first).strip()
        if len(first) > 40:
            first = first[:40]
        return first if first.endswith("？") else f"{first}？"

    def _compact_prompt(self, text: str) -> str:
        compact = self._clean_text(text)
        if not compact:
            return "请用 2-3 分钟回答，覆盖场景、方案、难点和结果。"
        parts = [part.strip(" -•·\t") for part in re.split(r"[。\n；;]", compact) if part.strip()]
        return "；".join(parts[:3])[:220]

    def _fallback_question_text(self, skill: str, target_position: str, difficulty: str) -> tuple[str, str]:
        templates = {
            "Redis": ("Redis 缓存一致性怎么处理？", "结合岗位场景说明缓存更新策略、失效风险和兜底方案。"),
            "MySQL": ("MySQL 慢查询怎么定位？", "说明索引、执行计划、数据量和 SQL 改写的排查顺序。"),
            "SQL": ("SQL 查询结果异常怎么排查？", "结合表结构、过滤条件、聚合逻辑和边界数据说明排查路径。"),
            "Java": ("Java 并发问题怎么定位？", "说明线程安全、锁、线程池和线上观测指标。"),
            "Python": ("Python 服务性能瓶颈怎么优化？", "结合 I/O、异步、批处理和监控指标说明方案。"),
            "PyTorch": ("PyTorch 训练效果不好怎么排查？", "说明数据、模型、损失函数、评估指标和实验对比。"),
            "算法": ("Top K 问题如何设计？", "说明数据结构选择、复杂度、边界条件和大数据场景。"),
        }
        if skill in templates:
            return templates[skill]
        if difficulty == "hard":
            return f"{skill} 线上故障怎么应对？", f"结合{target_position}场景，说明定位、止损、恢复和复盘。"
        if difficulty == "easy":
            return f"{skill} 的核心概念是什么？", "先解释定义，再说明适用场景和常见误区。"
        return f"{skill} 在项目中怎么落地？", "说明使用场景、关键实现、风险边界和结果验证。"

    def _local_question_blueprints(
        self,
        skills: list[str],
        target_position: str,
        difficulty: str,
        contexts: list[Any],
    ) -> list[tuple[str, str, list[str]]]:
        blueprints: list[tuple[str, str, list[str]]] = []
        for skill in skills:
            title, prompt = self._fallback_question_text(skill, target_position, difficulty)
            blueprints.append((title, prompt, [skill]))
        context_text = "\n".join(getattr(chunk, "text", "") for chunk in contexts)
        context_tags = list(dict.fromkeys(tag for chunk in contexts for tag in getattr(chunk, "skill_tags", [])))
        if any(word in context_text for word in ["RAG", "Agent", "检索", "切片"]):
            blueprints.append(
                (
                    "一个完整 Agent 一般包含哪些部分？",
                    "请说明规划、工具调用、记忆/上下文、状态管理、评估和安全边界。",
                    ["Agent", "RAG", "系统设计"],
                )
            )
        if any(word in context_text for word in ["Top K", "LRU", "复杂度", "算法"]):
            blueprints.append(
                (
                    "LRU 缓存如何做到 O(1)？",
                    "说明哈希表、双向链表、读写更新、淘汰策略和并发边界。",
                    ["算法", "数据结构"],
                )
            )
        if any(word in context_text for word in ["系统设计", "缓存", "队列", "幂等"]):
            blueprints.append(
                (
                    "高并发系统如何做降级和兜底？",
                    "请覆盖容量评估、缓存、队列、限流、降级、幂等和监控告警。",
                    ["系统设计", "并发"],
                )
            )
        if context_tags:
            title = f"{context_tags[0]} 面试高频点怎么准备？"
            prompt = "结合本地 RAG 命中的知识片段，说明核心概念、常见追问和项目中的落地证据。"
            blueprints.append((title, prompt, context_tags[:4]))
        return blueprints

    def _rag_sources(self, contexts: list[Any]) -> list[dict[str, str]]:
        sources = []
        seen = set()
        for chunk in contexts:
            key = (getattr(chunk, "repo", ""), getattr(chunk, "path", ""))
            if key in seen:
                continue
            seen.add(key)
            sources.append(
                {
                    "title": getattr(chunk, "title", ""),
                    "repo": getattr(chunk, "repo", ""),
                    "license": getattr(chunk, "license", ""),
                    "source_url": getattr(chunk, "source_url", ""),
                }
            )
        return sources[:4]

    def _clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

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
