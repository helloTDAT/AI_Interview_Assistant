from app.agents.question_agent import QuestionGenerationAgent
from app.agents.planner_agent import PlannerAgent
from app.core.storage import store
from app.models import ChatResponse
from app.services.ai_clients import LLMClient


class RouterAgent:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()
        self.question_agent = QuestionGenerationAgent()
        self.planner_agent = PlannerAgent()

    def route(self, user_id: str, message: str, target_position: str | None = None) -> ChatResponse:
        if self.planner_agent.should_plan(message):
            result = self.planner_agent.run(user_id, message, target_position or "后端开发工程师")
            payload = result.model_dump(mode="json")
            payload.update(result.data)
            return ChatResponse(intent="agent_plan", message=result.final_message, data=payload)
        intent = self.llm.classify_intent(message)
        if intent == "mock_interview":
            return ChatResponse(intent=intent, message="已识别为模拟面试需求。请调用 /interviews/mock/start 开始正式面试。")
        if intent == "resume_analysis":
            return ChatResponse(intent=intent, message="已识别为简历分析需求。请上传 PDF、DOCX 或图片简历到 /files/resume。")
        if intent == "audio_analysis":
            return ChatResponse(intent=intent, message="已识别为真实面试录音复盘需求。请上传录音到 /interviews/audio。")
        if intent == "learning_resource":
            report = store.resume_reports.get(user_id)
            profile = report["profile"] if report else None
            feed = self.question_agent.feed(user_id, profile, target_position or "后端开发工程师", limit=5)
            return ChatResponse(
                intent=intent,
                message="已为你准备个性化练习题瀑布流。",
                data={"questions": [q.model_dump(mode="json") for q in feed["questions"]]},
            )
        return ChatResponse(intent=intent, message="你好，我可以帮你分析简历、开始模拟面试、复盘真实录音或生成练习题。")
