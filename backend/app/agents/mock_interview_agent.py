from uuid import uuid4

from app.agents.question_agent import QuestionGenerationAgent
from app.core.storage import store
from app.models import MockInterviewResponse


class MockInterviewAgent:
    def __init__(self, question_agent: QuestionGenerationAgent | None = None) -> None:
        self.question_agent = question_agent or QuestionGenerationAgent()

    def start(self, user_id: str, target_position: str) -> MockInterviewResponse:
        report = store.resume_reports.get(user_id)
        profile = report["profile"] if report else None
        questions = self.question_agent.generate_for_resume(profile, target_position, count=5)
        session_id = str(uuid4())
        store.mock_sessions[session_id] = {
            "user_id": user_id,
            "target_position": target_position,
            "questions": questions,
            "answers": [],
            "index": 0,
        }
        return MockInterviewResponse(
            session_id=session_id,
            question=questions[0].title,
            round_index=1,
        )

    def answer(self, session_id: str, answer: str) -> MockInterviewResponse:
        session = store.mock_sessions[session_id]
        session["answers"].append(answer)
        current_question = session["questions"][session["index"]]
        feedback = self._feedback(answer, current_question.skill_tags)
        session["index"] += 1
        if session["index"] >= len(session["questions"]):
            return MockInterviewResponse(
                session_id=session_id,
                question="本轮模拟面试已结束。请查看总结反馈。",
                feedback=feedback + " 总结：建议继续强化结构化表达和岗位技能案例。",
                round_index=session["index"],
                finished=True,
            )
        next_question = session["questions"][session["index"]]
        follow_up = "请进一步补充量化结果。" if len(answer) < 50 else next_question.title
        return MockInterviewResponse(
            session_id=session_id,
            question=follow_up,
            feedback=feedback,
            round_index=session["index"] + 1,
        )

    def _feedback(self, answer: str, skill_tags: list[str]) -> str:
        if len(answer.strip()) < 20:
            return "回答偏短，建议按 STAR 结构补充背景、行动和结果。"
        if any(word in answer for word in ["提升", "降低", "%", "用户", "性能", "指标"]):
            return "回答包含结果意识，建议继续补充个人职责和关键决策。"
        skill_hint = f"，并突出 {skill_tags[0]}" if skill_tags else ""
        return f"表达基本完整，建议增加量化结果{skill_hint}。"
