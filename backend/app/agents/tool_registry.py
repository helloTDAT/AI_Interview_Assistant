from __future__ import annotations

from typing import Any

from app.agents.mock_interview_agent import MockInterviewAgent
from app.agents.question_agent import QuestionGenerationAgent
from app.core.storage import get_active_resume_report, store
from app.models import AgentToolTrace
from app.services.ai_clients import LLMClient
from app.services.learning_rag import LearningRagService


class ToolRegistry:
    """Small tool layer that wraps existing Agents without adding new vendors."""

    def __init__(
        self,
        llm: LLMClient | None = None,
        question_agent: QuestionGenerationAgent | None = None,
        mock_agent: MockInterviewAgent | None = None,
        rag: LearningRagService | None = None,
    ) -> None:
        self.llm = llm or LLMClient()
        self.question_agent = question_agent or QuestionGenerationAgent()
        self.mock_agent = mock_agent or MockInterviewAgent(question_agent=self.question_agent, llm=self.llm)
        self.rag = rag or LearningRagService(self.llm)

    def classify_intent(self, message: str) -> tuple[AgentToolTrace, dict[str, Any]]:
        intent = self.llm.classify_intent(message)
        return (
            AgentToolTrace(tool_name="classify_intent", status="completed", summary=f"识别到意图：{intent}。"),
            {"intent": intent},
        )

    def get_resume_profile(self, user_id: str) -> tuple[AgentToolTrace, dict[str, Any]]:
        report = get_active_resume_report(user_id)
        if not report:
            return (
                AgentToolTrace(
                    tool_name="get_resume_profile",
                    status="fallback",
                    summary="当前会话还没有可用的简历画像。",
                    fallback="请先挂载简历并发送分析需求，Planner 不会伪造简历内容。",
                ),
                {"profile": None},
            )
        profile = report.get("profile") if isinstance(report, dict) else None
        skills = profile.get("skills", []) if isinstance(profile, dict) else []
        return (
            AgentToolTrace(
                tool_name="get_resume_profile",
                status="completed",
                summary=f"已读取简历画像，技能线索 {len(skills)} 项。",
            ),
            {"profile": profile},
        )

    def search_rag(self, query: str, target_position: str) -> tuple[AgentToolTrace, dict[str, Any]]:
        chunks = self.rag.search(f"{target_position} {query}", top_k=3)
        return (
            AgentToolTrace(
                tool_name="search_rag",
                status="completed",
                summary=f"本地 RAG 命中 {len(chunks)} 条知识片段。",
            ),
            {"chunks": [chunk.model_dump(mode="json") for chunk in chunks]},
        )

    def generate_learning_feed(
        self,
        user_id: str,
        profile: dict | None,
        target_position: str,
        limit: int = 5,
    ) -> tuple[AgentToolTrace, dict[str, Any]]:
        result = self.question_agent.feed(user_id, profile, target_position, limit=limit)
        questions = [question.model_dump(mode="json") for question in result["questions"]]
        return (
            AgentToolTrace(
                tool_name="generate_learning_feed",
                status="completed",
                summary=f"已生成 {len(questions)} 道练习题推荐。",
            ),
            {
                "questions": questions,
                "insights": [node.model_dump(mode="json") for node in result["insights"]],
                "rag_status": result["rag_status"],
            },
        )

    def start_mock_interview(self, user_id: str, target_position: str) -> tuple[AgentToolTrace, dict[str, Any]]:
        response = self.mock_agent.start(user_id, target_position)
        return (
            AgentToolTrace(
                tool_name="start_mock_interview",
                status="completed",
                summary="已创建模拟面试 session。",
            ),
            {"mock_interview": response.model_dump(mode="json")},
        )

    def summarize_context(self, payload: dict[str, Any]) -> tuple[AgentToolTrace, dict[str, Any]]:
        has_resume = bool(payload.get("profile"))
        retrieved = len(payload.get("chunks") or [])
        summary = f"上下文：{'已有简历画像' if has_resume else '暂无简历画像'}，RAG 命中 {retrieved} 条。"
        return (
            AgentToolTrace(tool_name="summarize_context", status="completed", summary=summary),
            {"context_summary": summary},
        )
