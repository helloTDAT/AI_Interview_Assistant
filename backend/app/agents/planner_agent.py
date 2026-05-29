from __future__ import annotations

from typing import Any

from app.agents.tool_registry import ToolRegistry
from app.models import AgentPlan, AgentPlanResponse, AgentPlanStep


class PlannerAgent:
    planning_keywords = ["规划", "计划", "路径", "安排", "先", "再", "然后", "准备", "训练", "练习计划"]

    def __init__(self, tools: ToolRegistry | None = None) -> None:
        self.tools = tools or ToolRegistry()

    def should_plan(self, message: str) -> bool:
        return any(keyword in message for keyword in self.planning_keywords)

    def run(self, user_id: str, message: str, target_position: str = "后端开发工程师") -> AgentPlanResponse:
        steps = self._build_steps(message)
        traces = []
        data: dict[str, Any] = {}

        trace, payload = self.tools.classify_intent(message)
        traces.append(trace)
        data.update(payload)
        self._mark_step(steps, "classify_intent", trace.status)

        profile = None
        if self._needs_resume_context(message):
            trace, payload = self.tools.get_resume_profile(user_id)
            traces.append(trace)
            profile = payload.get("profile")
            data.update(payload)
            self._mark_step(steps, "get_resume_profile", trace.status)

        if self._needs_rag(message):
            trace, payload = self.tools.search_rag(message, target_position)
            traces.append(trace)
            data.update(payload)
            self._mark_step(steps, "search_rag", trace.status)

        if self._needs_learning_feed(message):
            trace, payload = self.tools.generate_learning_feed(user_id, profile, target_position)
            traces.append(trace)
            data.update(payload)
            self._mark_step(steps, "generate_learning_feed", trace.status)

        if self._needs_mock_start(message):
            trace, payload = self.tools.start_mock_interview(user_id, target_position)
            traces.append(trace)
            data.update(payload)
            self._mark_step(steps, "start_mock_interview", trace.status)

        trace, payload = self.tools.summarize_context(data)
        traces.append(trace)
        data.update(payload)
        self._mark_step(steps, "summarize_context", trace.status)

        plan = AgentPlan(
            user_goal=message,
            context_summary=data.get("context_summary", "Planner 已完成上下文整理。"),
            steps=steps,
        )
        return AgentPlanResponse(
            plan=plan,
            traces=traces,
            final_message=self._final_message(steps, data),
            data=data,
        )

    def _build_steps(self, message: str) -> list[AgentPlanStep]:
        steps = [
            AgentPlanStep(name="识别用户目标", tool_name="classify_intent", input_summary="用户自然语言请求"),
        ]
        if self._needs_resume_context(message):
            steps.append(AgentPlanStep(name="读取简历画像", tool_name="get_resume_profile", input_summary="当前 user_id"))
        if self._needs_rag(message):
            steps.append(AgentPlanStep(name="检索面试宝典", tool_name="search_rag", input_summary="目标岗位与用户目标"))
        if self._needs_learning_feed(message):
            steps.append(AgentPlanStep(name="生成练习推荐", tool_name="generate_learning_feed", input_summary="岗位、简历画像、RAG"))
        if self._needs_mock_start(message):
            steps.append(AgentPlanStep(name="创建模拟面试", tool_name="start_mock_interview", input_summary="目标岗位"))
        steps.append(AgentPlanStep(name="汇总执行上下文", tool_name="summarize_context", input_summary="工具结果"))
        return steps

    def _needs_resume_context(self, message: str) -> bool:
        return any(keyword in message for keyword in ["简历", "我的", "个性化", "练习计划", "准备"])

    def _needs_rag(self, message: str) -> bool:
        return any(keyword in message for keyword in ["面试", "题", "知识", "宝典", "准备", "练习", "训练"])

    def _needs_learning_feed(self, message: str) -> bool:
        return any(keyword in message for keyword in ["练习", "刷题", "题", "训练", "学习", "准备"])

    def _needs_mock_start(self, message: str) -> bool:
        return "开始模拟面试" in message or ("模拟面试" in message and "开始" in message)

    def _mark_step(self, steps: list[AgentPlanStep], tool_name: str, status: str) -> None:
        for step in steps:
            if step.tool_name == tool_name:
                step.status = status
                return

    def _final_message(self, steps: list[AgentPlanStep], data: dict[str, Any]) -> str:
        completed = sum(1 for step in steps if step.status == "completed")
        fallback = [step for step in steps if step.status == "fallback"]
        questions = data.get("questions") or []
        message = f"Agent 已规划 {len(steps)} 步，已完成 {completed} 步。"
        if questions:
            message += f" 已生成 {len(questions)} 道练习题，可直接进入练习。"
        if fallback:
            message += " 有步骤使用了安全 fallback，请先补齐缺失上下文。"
        return message
