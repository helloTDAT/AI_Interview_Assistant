from __future__ import annotations

import re
from typing import Any, Literal, TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph

from app.agents.question_agent import QuestionGenerationAgent
from app.core.storage import store
from app.models import MockInterviewResponse, ResumeProfile
from app.services.ai_clients import LLMClient


InterviewStateName = Literal[
    "Greeting",
    "ListeningParsing",
    "DecisionMaking",
    "Probing",
    "NewQuestion",
    "ReverseQA",
    "Closing",
]


class InterviewGraphState(TypedDict, total=False):
    session: dict[str, Any]
    answer: str
    keywords: list[str]
    depth_score: int
    pressure_level: int
    decision: str
    response: dict[str, Any]


MODE_LABELS = {
    "tech_blitz": "技术快问快答",
    "project_deep_dive": "综合模拟面试",
    "behavioral": "行为与抗压测试",
}

TECH_TERMS = [
    "Agent",
    "RAG",
    "Python",
    "Java",
    "PyTorch",
    "TensorFlow",
    "Mamba",
    "模型",
    "MySQL",
    "Redis",
    "Netty",
    "RocketMQ",
    "Zookeeper",
    "Spring",
    "Docker",
    "Linux",
    "SQL",
    "HTTP",
    "线程",
    "事务",
    "索引",
    "缓存",
    "复杂度",
    "系统设计",
]


class MockInterviewAgent:
    def __init__(
        self,
        question_agent: QuestionGenerationAgent | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.question_agent = question_agent or QuestionGenerationAgent()
        self.llm = llm or LLMClient()
        self.graph = self._build_graph()

    def start(
        self,
        user_id: str,
        target_position: str,
        mode: str = "project_deep_dive",
    ) -> MockInterviewResponse:
        mode = self._normalize_mode(mode)
        report = store.resume_reports.get(user_id)
        profile = report["profile"] if report else None
        resume_context = self._resume_context(profile)
        anchor_project = self._select_anchor_project(resume_context, target_position)
        has_resume_context = bool(anchor_project)
        resume_questions = (
            self.question_agent.generate_for_resume(profile, target_position, count=3)
            if has_resume_context
            else []
        )
        plan = self._build_interview_plan(target_position, mode, resume_context, resume_questions, anchor_project)
        first_item = plan[0]
        session_id = str(uuid4())
        store.mock_sessions[session_id] = {
            "user_id": user_id,
            "target_position": target_position,
            "mode": mode,
            "resume_context": resume_context,
            "anchor_project": anchor_project,
            "has_resume_context": has_resume_context,
            "plan": plan,
            "plan_index": 0,
            "current_question": first_item,
            "answers": [],
            "turns": [
                {
                    "role": "interviewer",
                    "text": first_item["question"],
                    "state": "Greeting",
                    "question_type": first_item["question_type"],
                }
            ],
            "probe_count": 0,
            "reverse_asked": False,
            "finished": False,
            "finish_response": None,
            "max_rounds": len(plan),
            "skill_scores": {
                "项目表达": 50,
                "岗位基础": 50,
                "计算机基础": 50,
                "算法思维": 50,
                "系统设计": 50,
                "临场应变": 50,
            },
        }
        return MockInterviewResponse(
            session_id=session_id,
            question=first_item["question"],
            feedback=f"已进入{MODE_LABELS[mode]}，当前岗位：{target_position}。",
            round_index=1,
            round_total=len(plan),
            state="Greeting",
            mode=mode,
            question_type=first_item["question_type"],
            phase_label=first_item["phase_label"],
            anchor_project=anchor_project,
            difficulty_level=first_item["difficulty_level"],
            question_intent=first_item["question_intent"],
            pressure_level=38 if mode != "behavioral" else 52,
            detected_keywords=first_item.get("expected_terms", [])[:5],
            skill_scores=store.mock_sessions[session_id]["skill_scores"],
        )

    def answer(self, session_id: str, answer: str) -> MockInterviewResponse:
        session = store.mock_sessions[session_id]
        if session.get("finished"):
            return MockInterviewResponse(**self._stored_finish_response(session))
        session["answers"].append({"question": session["current_question"], "answer": answer})
        state: InterviewGraphState = {"session": session, "answer": answer}
        result = self.graph.invoke(state)
        response = result["response"]
        if response.get("finished"):
            session["finished"] = True
            session["ended_reason"] = "completed"
            session["finish_response"] = response
        session["turns"].append({"role": "candidate", "text": answer})
        session["turns"].append(
            {
                "role": "interviewer",
                "text": response["question"],
                "state": response["state"],
                "question_type": response["question_type"],
            }
        )
        return MockInterviewResponse(**response)

    def finish(self, session_id: str, reason: str = "user_requested") -> MockInterviewResponse:
        session = store.mock_sessions[session_id]
        if session.get("finished"):
            return MockInterviewResponse(**self._stored_finish_response(session))

        current = session.get("current_question", {})
        state: InterviewGraphState = {
            "session": session,
            "answer": "",
            "keywords": current.get("expected_terms", [])[:5],
            "depth_score": 0,
            "pressure_level": 20,
        }
        report = self._final_report(session, state, include_current=False)
        completed = len(session.get("answers", []))
        if completed < session.get("max_rounds", 8):
            report = {
                **report,
                "summary": f"本轮提前结束，基于已完成 {completed}/{session.get('max_rounds', 8)} 个回合评估。{report['summary']}",
            }
        response = self._base_response(
            session,
            question="本轮沉浸式模拟面试已结束。你可以查看右侧能力图谱，并选择继续练习薄弱项。",
            feedback=report["summary"],
            state_name="Closing",
            question_type="summary",
            depth_score=0,
            pressure_level=20,
            probing_reason="用户主动结束面试，已基于当前回合生成即时复盘。",
            keywords=current.get("expected_terms", [])[:5],
            finished=True,
            final_report=report,
        )
        session["finished"] = True
        session["ended_reason"] = reason
        session["finish_response"] = response
        session["turns"].append(
            {
                "role": "interviewer",
                "text": response["question"],
                "state": response["state"],
                "question_type": response["question_type"],
            }
        )
        return MockInterviewResponse(**response)

    def _build_graph(self):
        graph = StateGraph(InterviewGraphState)
        graph.add_node("ListeningParsing", self._parse_answer)
        graph.add_node("DecisionMaking", self._decide_next)
        graph.add_node("Probing", self._probe)
        graph.add_node("NewQuestion", self._new_question)
        graph.add_node("ReverseQA", self._reverse_qa)
        graph.add_node("Closing", self._closing)
        graph.set_entry_point("ListeningParsing")
        graph.add_edge("ListeningParsing", "DecisionMaking")
        graph.add_conditional_edges(
            "DecisionMaking",
            lambda state: state["decision"],
            {
                "probe": "Probing",
                "new_question": "NewQuestion",
                "reverse_qa": "ReverseQA",
                "closing": "Closing",
            },
        )
        graph.add_edge("Probing", END)
        graph.add_edge("NewQuestion", END)
        graph.add_edge("ReverseQA", END)
        graph.add_edge("Closing", END)
        return graph.compile()

    def _parse_answer(self, state: InterviewGraphState) -> InterviewGraphState:
        answer = state.get("answer", "")
        session = state["session"]
        current = session.get("current_question", {})
        keywords = self._keywords(answer, current)
        depth_score = self._depth_score(answer, keywords, current)
        pressure_level = self._pressure(depth_score, len(session["answers"]), session["mode"])
        return {**state, "keywords": keywords, "depth_score": depth_score, "pressure_level": pressure_level}

    def _decide_next(self, state: InterviewGraphState) -> InterviewGraphState:
        session = state["session"]
        if session.get("reverse_asked"):
            return {**state, "decision": "closing"}
        if state["depth_score"] < 58 and session["probe_count"] < 1:
            session["probe_count"] += 1
            return {**state, "decision": "probe"}
        if session["plan_index"] >= len(session["plan"]) - 1:
            session["reverse_asked"] = True
            return {**state, "decision": "reverse_qa"}
        return {**state, "decision": "new_question"}

    def _probe(self, state: InterviewGraphState) -> InterviewGraphState:
        session = state["session"]
        response = self._llm_turn(state, "probe") if session.get("has_resume_context") else None
        response = response or self._rule_probe(state)
        session["skill_scores"] = self._updated_scores(session["skill_scores"], state)
        return {**state, "response": {**response, "skill_scores": session["skill_scores"]}}

    def _new_question(self, state: InterviewGraphState) -> InterviewGraphState:
        session = state["session"]
        session["plan_index"] = min(session["plan_index"] + 1, len(session["plan"]) - 1)
        session["current_question"] = session["plan"][session["plan_index"]]
        session["probe_count"] = 0
        session["skill_scores"] = self._updated_scores(session["skill_scores"], state)
        item = session["current_question"]
        response = self._base_response(
            session,
            question=item["question"],
            feedback=self._feedback_text(state),
            state_name="NewQuestion",
            question_type=item["question_type"],
            depth_score=state["depth_score"],
            pressure_level=state["pressure_level"],
            probing_reason=f"进入下一阶段：{item['phase_label']}。",
            keywords=item.get("expected_terms", [])[:6],
        )
        return {**state, "response": response}

    def _reverse_qa(self, state: InterviewGraphState) -> InterviewGraphState:
        session = state["session"]
        session["skill_scores"] = self._updated_scores(session["skill_scores"], state)
        response = self._base_response(
            session,
            question="我的问题先到这里。现在轮到你反向提问：你有什么想了解团队、业务、技术体系或岗位成长的吗？",
            feedback="前面的回答我已经记录。反向提问也会计入沟通质量与业务理解。",
            state_name="ReverseQA",
            question_type="reverse_qa",
            depth_score=state["depth_score"],
            pressure_level=45,
            probing_reason="8 个核心回合已完成，进入候选人反向提问环节。",
            keywords=state.get("keywords", []),
            reverse_question_prompt="请提出一个你会在真实面试结尾问面试官的问题。",
        )
        return {**state, "response": response}

    def _closing(self, state: InterviewGraphState) -> InterviewGraphState:
        session = state["session"]
        report = self._final_report(session, state)
        response = self._base_response(
            session,
            question="本轮沉浸式模拟面试已结束。你可以查看右侧能力图谱，并选择继续练习薄弱项。",
            feedback=report["summary"],
            state_name="Closing",
            question_type="summary",
            depth_score=state["depth_score"],
            pressure_level=20,
            probing_reason="已完成反向提问和总结复盘。",
            keywords=state.get("keywords", []),
            finished=True,
            final_report=report,
        )
        return {**state, "response": response}

    def _rule_probe(self, state: InterviewGraphState) -> dict[str, Any]:
        session = state["session"]
        current = session.get("current_question", {})
        missing = self._missing_expected_terms(state.get("answer", ""), current)
        if missing:
            question = f"这里先补一个基础澄清：你刚才没有展开「{missing[0]}」。请用一个具体例子说明它在当前问题中的作用、边界和风险。"
        elif current.get("question_type", "").startswith("project"):
            question = "你刚才的项目回答还偏概括。请具体到一个模块：输入是什么、处理链路是什么、你写了哪些关键逻辑，最后怎么验证有效？"
        elif current.get("question_type") == "algorithm":
            question = "请把算法思路进一步具体化：数据结构怎么选，时间复杂度是多少，最大输入规模和异常边界怎么处理？"
        else:
            question = "请不要只给结论。请补充定义、适用场景、关键步骤和一个容易出错的边界条件。"
        return self._base_response(
            session,
            question=question,
            feedback=self._feedback_text(state),
            state_name="Probing",
            question_type=current.get("question_type", "technical"),
            depth_score=state["depth_score"],
            pressure_level=state["pressure_level"],
            probing_reason=self._probing_reason(state),
            keywords=state.get("keywords") or current.get("expected_terms", [])[:5],
        )

    def _llm_turn(self, state: InterviewGraphState, decision: str) -> dict[str, Any] | None:
        session = state["session"]
        current = session.get("current_question", {})
        result = self.llm.generate_mock_interview_turn(
            {
                "decision_hint": decision,
                "target_position": session["target_position"],
                "mode": session["mode"],
                "resume_context": session["resume_context"],
                "anchor_project": session.get("anchor_project"),
                "current_question": current,
                "instruction": "只能基于简历锚点、当前问题和候选人上一轮回答继续追问；不要把章节标题当作项目。",
                "turn_count": len(session["answers"]),
                "answer": state.get("answer", ""),
                "keywords": state.get("keywords", []),
                "depth_score": state.get("depth_score", 0),
            }
        )
        if not result.ok or not isinstance(result.data, dict):
            return None
        question = str(result.data.get("question") or "").strip()
        if not question or self._looks_like_heading(question):
            return None
        return self._base_response(
            session,
            question=question,
            feedback=str(result.data.get("feedback") or self._feedback_text(state)),
            state_name="Probing",
            question_type=current.get("question_type", "technical"),
            depth_score=state["depth_score"],
            pressure_level=self._clamp(result.data.get("pressure_level"), state["pressure_level"]),
            probing_reason=str(result.data.get("probing_reason") or self._probing_reason(state)),
            keywords=self._strings(result.data.get("detected_keywords")) or state.get("keywords", []),
        )

    def _base_response(
        self,
        session: dict[str, Any],
        *,
        question: str,
        feedback: str,
        state_name: InterviewStateName,
        question_type: str,
        depth_score: int,
        pressure_level: int,
        probing_reason: str | None = None,
        keywords: list[str] | None = None,
        reverse_question_prompt: str | None = None,
        finished: bool = False,
        final_report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        item = session.get("current_question", {})
        return {
            "session_id": self._session_id(session),
            "question": question,
            "feedback": feedback,
            "round_index": min(session.get("plan_index", 0) + 1, session["max_rounds"]),
            "round_total": session["max_rounds"],
            "finished": finished,
            "state": state_name,
            "mode": session["mode"],
            "question_type": question_type,
            "phase_label": item.get("phase_label"),
            "anchor_project": session.get("anchor_project"),
            "difficulty_level": item.get("difficulty_level"),
            "question_intent": item.get("question_intent"),
            "probing_reason": probing_reason,
            "detected_keywords": keywords or [],
            "pressure_level": pressure_level,
            "answer_depth_score": depth_score,
            "reverse_question_prompt": reverse_question_prompt,
            "final_report": final_report,
        }

    def _stored_finish_response(self, session: dict[str, Any]) -> dict[str, Any]:
        response = session.get("finish_response")
        if isinstance(response, dict):
            return response
        state: InterviewGraphState = {
            "session": session,
            "answer": "",
            "keywords": [],
            "depth_score": 0,
            "pressure_level": 20,
        }
        report = self._final_report(session, state, include_current=False)
        return self._base_response(
            session,
            question="本轮沉浸式模拟面试已结束。你可以查看右侧能力图谱，并选择继续练习薄弱项。",
            feedback=report["summary"],
            state_name="Closing",
            question_type="summary",
            depth_score=0,
            pressure_level=20,
            probing_reason="本轮面试已经结束。",
            keywords=[],
            finished=True,
            final_report=report,
        )

    def _build_interview_plan(
        self,
        target_position: str,
        mode: str,
        resume_context: dict[str, Any],
        resume_questions: list[Any],
        anchor_project: str | None,
    ) -> list[dict[str, Any]]:
        role_questions = self._role_questions(target_position)
        if mode == "tech_blitz":
            return [
                role_questions["role_core"],
                role_questions["role_core_2"],
                self._cs_foundation_question(target_position),
                role_questions["cache_or_model"],
                role_questions["algorithm"],
                role_questions["system_design"],
                role_questions["troubleshooting"],
                role_questions["open"],
            ]
        if mode == "behavioral":
            plan = [
                role_questions["behavioral"],
                role_questions["open"],
                role_questions["troubleshooting"],
                self._cs_foundation_question(target_position),
                role_questions["system_design"],
                role_questions["algorithm"],
                role_questions["role_core"],
                role_questions["behavioral_pressure"],
            ]
            if anchor_project:
                plan[1] = self._project_question("project_warmup", "项目暖场", anchor_project, target_position, resume_context)
            return plan
        if anchor_project:
            return [
                self._project_question("project_warmup", "项目暖场", anchor_project, target_position, resume_context),
                self._project_question("project_basic", "项目基础", anchor_project, target_position, resume_context),
                self._project_question("project_tech_basic", "项目技术基础", anchor_project, target_position, resume_context),
                self._project_question("project_implementation", "项目实现细节", anchor_project, target_position, resume_context),
                self._project_question("project_deep", "项目深挖", anchor_project, target_position, resume_context),
                self._cs_foundation_question(target_position),
                role_questions["algorithm"],
                role_questions["system_design"],
            ]
        return [
            role_questions["role_core"],
            role_questions["role_overview"],
            self._cs_foundation_question(target_position),
            role_questions["cache_or_model"],
            role_questions["algorithm"],
            role_questions["system_design"],
            role_questions["open"],
            role_questions["behavioral"],
        ]

    def _project_question(
        self,
        question_type: str,
        phase_label: str,
        anchor_project: str,
        target_position: str,
        resume_context: dict[str, Any],
    ) -> dict[str, Any]:
        anchor = self._short_anchor(anchor_project, 90)
        terms = self._anchor_terms(anchor_project, resume_context)
        templates = {
            "project_warmup": (
                f"我们先从简历项目开始。请用 1 分钟介绍「{anchor}」：它的业务背景是什么，你承担的职责是什么，最后产生了什么结果，它如何支撑你应聘{target_position}？",
                "确认候选人是否能清楚讲出真实经历的背景、职责和结果。",
                "easy",
            ),
            "project_basic": (
                f"围绕「{anchor}」，请说明这个项目的核心模块边界、主要技术栈、关键调用链或数据流分别是什么。",
                "考察项目整体理解和模块拆解能力。",
                "medium",
            ),
            "project_tech_basic": (
                f"从这个项目里选一个最关键的技术点（例如 {self._example_terms(terms)}），解释它的基础原理、适用场景和为什么在这里使用。",
                "先问项目相关基础原理，避免直接跳到高压深挖。",
                "medium",
            ),
            "project_implementation": (
                f"继续看「{anchor}」的实现细节。请讲一个你亲自负责的模块：接口或数据结构怎么设计，并发、错误重试、资源隔离或部署如何处理？",
                "考察是否真正做过实现，而不是只会讲项目概述。",
                "hard",
            ),
            "project_deep": (
                f"这个项目最大的难点或瓶颈是什么？请说明你的取舍依据、验证方式、性能/稳定性指标，以及如果重做你会如何优化。",
                "进入项目深挖，考察指标、风险、复盘和架构取舍。",
                "hard",
            ),
        }
        question, intent, difficulty = templates[question_type]
        return self._plan_item("project", phase_label, question, terms, difficulty, intent)

    def _role_questions(self, target_position: str) -> dict[str, dict[str, Any]]:
        if self._is_ai_role(target_position):
            return {
                "role_overview": self._plan_item(
                    "role_core",
                    "岗位认知",
                    f"你理解的{target_position}核心能力是什么？一个完整的 Agent 智能体一般包含哪些部分？请从模型、数据、工程落地和评估四个角度说明。",
                    ["Agent", "模型", "数据", "工程", "评估"],
                    "easy",
                    "无简历时先确认岗位认知，不假设项目经历。",
                ),
                "role_core": self._plan_item(
                    "role_core",
                    "岗位基础",
                    "一个完整的 Agent 智能体一般包含哪些部分？请说明感知、规划、记忆、工具调用、执行和反馈分别承担什么职责。",
                    ["Agent", "规划", "记忆", "工具调用", "反馈"],
                    "medium",
                    "考察 AI/算法岗基础概念。",
                ),
                "role_core_2": self._plan_item(
                    "role_core",
                    "岗位基础",
                    "RAG 系统里向量检索、召回、重排和生成分别解决什么问题？如果回答不准，你会先排查哪里？",
                    ["RAG", "向量", "召回", "重排", "生成"],
                    "medium",
                    "考察检索增强生成链路理解。",
                ),
                "cache_or_model": self._plan_item(
                    "foundation",
                    "模型工程基础",
                    "训练或推理链路变慢时，你会如何定位是数据、模型、硬件还是服务编排问题？",
                    ["数据", "模型", "GPU", "服务", "指标"],
                    "medium",
                    "考察工程化定位能力。",
                ),
                "algorithm": self._plan_item(
                    "algorithm",
                    "算法思维",
                    "给你一批用户行为日志，如何找出最近 7 天连续活跃的用户？请说明数据结构、复杂度和边界情况。",
                    ["哈希", "窗口", "复杂度", "边界"],
                    "medium",
                    "考察编码和复杂度意识。",
                ),
                "system_design": self._plan_item(
                    "system_design",
                    "系统设计",
                    "如果要设计一个可扩展的面试问答 Agent 服务，你会如何设计会话状态、工具调用、失败重试和监控指标？",
                    ["会话", "工具", "重试", "监控"],
                    "hard",
                    "考察 AI 应用系统设计。",
                ),
                "troubleshooting": self._plan_item(
                    "system_design",
                    "问题定位",
                    "线上 Agent 回答突然变差，你会如何区分是提示词、检索、模型、数据还是服务链路的问题？",
                    ["提示词", "检索", "模型", "数据", "链路"],
                    "hard",
                    "考察问题拆解。",
                ),
                "open": self._plan_item(
                    "open",
                    "开放问题",
                    "如果业务方希望模型效果更好但数据质量很差，你会如何拆解问题、设定实验，并和业务方对齐预期？",
                    ["数据质量", "实验", "指标", "业务"],
                    "medium",
                    "考察业务沟通和方案拆解。",
                ),
                "behavioral": self._plan_item(
                    "behavioral",
                    "行为沟通",
                    "如果你和同学或同事在模型路线选择上有明显分歧，你会如何推动共识？",
                    ["分歧", "共识", "证据", "沟通"],
                    "medium",
                    "考察行为面试 STAR 表达。",
                ),
                "behavioral_pressure": self._plan_item(
                    "behavioral",
                    "行为抗压",
                    "如果你负责的模型上线后效果不稳定，业务方质疑方案价值，你会如何止损、复盘并推进下一步？",
                    ["止损", "复盘", "沟通", "指标"],
                    "hard",
                    "考察压力场景应对。",
                ),
            }
        return {
            "role_overview": self._plan_item(
                "role_core",
                "岗位认知",
                f"你理解的{target_position}核心能力是什么？请从接口、数据、稳定性和协作四个角度说明。",
                ["接口", "数据", "稳定性", "协作"],
                "easy",
                "无简历时先确认岗位认知，不假设项目经历。",
            ),
            "role_core": self._plan_item(
                "role_core",
                "岗位基础",
                "一次 HTTP 请求从浏览器到后端服务，大致会经过哪些环节？如果接口变慢，你会从哪里定位？",
                ["HTTP", "网络", "服务", "数据库", "定位"],
                "medium",
                "考察后端基础链路。",
            ),
            "role_core_2": self._plan_item(
                "role_core",
                "岗位基础",
                "Redis 缓存雪崩、击穿和穿透有什么区别？分别适合用什么方案处理？",
                ["Redis", "雪崩", "击穿", "穿透", "过期"],
                "medium",
                "考察缓存基础。",
            ),
            "cache_or_model": self._plan_item(
                "foundation",
                "后端基础",
                "MySQL 索引为什么能加速查询？联合索引什么时候会失效？你会如何判断一个慢查询该不该加索引？",
                ["MySQL", "索引", "联合索引", "慢查询"],
                "medium",
                "考察数据库基础。",
            ),
            "algorithm": self._plan_item(
                "algorithm",
                "算法思维",
                "如何在一个很大的整数数组里找 Top K 高频元素？请说明思路、复杂度和边界情况。",
                ["哈希", "堆", "Top K", "复杂度"],
                "medium",
                "考察编码和复杂度意识。",
            ),
            "system_design": self._plan_item(
                "system_design",
                "系统设计",
                "如果一个单体系统要逐步演进到高并发架构，你会优先改哪几部分？为什么？",
                ["高并发", "缓存", "队列", "拆分", "观测"],
                "hard",
                "考察架构取舍。",
            ),
            "troubleshooting": self._plan_item(
                "system_design",
                "问题定位",
                "线上接口 P99 延迟突然升高，你会按什么顺序排查网络、应用、线程池、数据库和缓存？",
                ["P99", "线程池", "数据库", "缓存", "链路"],
                "hard",
                "考察故障定位能力。",
            ),
            "open": self._plan_item(
                "open",
                "开放问题",
                "如果需求很急但你判断当前方案会留下明显技术债，你会怎么沟通、拆分和交付？",
                ["沟通", "技术债", "拆分", "交付"],
                "medium",
                "考察工程判断。",
            ),
            "behavioral": self._plan_item(
                "behavioral",
                "行为沟通",
                "线上故障发生后，你会如何组织排查、止损、复盘和预防？",
                ["故障", "止损", "复盘", "预防"],
                "medium",
                "考察行为面试 STAR 表达。",
            ),
            "behavioral_pressure": self._plan_item(
                "behavioral",
                "行为抗压",
                "如果你负责的改造延期并影响其他同学联调，你会如何同步风险、调整计划并恢复信任？",
                ["延期", "风险", "计划", "信任"],
                "hard",
                "考察压力场景应对。",
            ),
        }

    def _cs_foundation_question(self, target_position: str) -> dict[str, Any]:
        if self._is_ai_role(target_position):
            return self._plan_item(
                "foundation",
                "计算机基础",
                "数据库索引为什么能加速查询？在哪些情况下索引可能失效，机器学习特征查询场景里你会如何设计索引？",
                ["索引", "查询", "选择性", "失效", "特征"],
                "medium",
                "考察计算机基础和岗位结合能力。",
            )
        return self._plan_item(
            "foundation",
            "计算机基础",
            "进程和线程有什么区别？在高并发服务里，线程池使用不当可能带来哪些问题？",
            ["进程", "线程", "线程池", "并发", "资源"],
            "medium",
            "考察操作系统与并发基础。",
        )

    def _plan_item(
        self,
        question_type: str,
        phase_label: str,
        question: str,
        expected_terms: list[str],
        difficulty_level: str = "medium",
        question_intent: str = "",
    ) -> dict[str, Any]:
        return {
            "question_type": question_type,
            "category_label": phase_label,
            "phase_label": phase_label,
            "question": question,
            "expected_terms": expected_terms,
            "difficulty_level": difficulty_level,
            "question_intent": question_intent,
        }

    def _resume_context(self, profile: ResumeProfile | dict | None) -> dict[str, Any]:
        if isinstance(profile, ResumeProfile):
            return {
                "projects": profile.projects[:5],
                "internships": profile.internships[:3],
                "skills": profile.skills[:12],
                "raw_text": profile.raw_text[:1800],
            }
        if isinstance(profile, dict):
            return {
                "projects": [str(item) for item in profile.get("projects", [])][:5],
                "internships": [str(item) for item in profile.get("internships", [])][:3],
                "skills": [str(item) for item in profile.get("skills", [])][:12],
                "raw_text": str(profile.get("raw_text", ""))[:1800],
            }
        return {"projects": [], "internships": [], "skills": [], "raw_text": ""}

    def _select_anchor_project(self, resume_context: dict[str, Any], target_position: str) -> str | None:
        candidates = [*resume_context.get("projects", []), *resume_context.get("internships", [])]
        ranked: list[tuple[int, str]] = []
        role_terms = self._role_anchor_terms(target_position)
        for item in candidates:
            text = self._clean_anchor(str(item))
            if not text or self._looks_like_heading(text):
                continue
            score = 0
            score += sum(6 for term in role_terms if term.lower() in text.lower())
            score += sum(3 for term in resume_context.get("skills", []) if term.lower() in text.lower())
            score += 8 if re.search(r"\d|%|QPS|TPS|ms|秒|万|fps", text, re.I) else 0
            score += 8 if any(word in text for word in ["负责", "主导", "设计", "实现", "优化", "重构", "迁移", "压测", "部署"]) else 0
            score += min(10, len(text) // 80)
            if score >= 8:
                ranked.append((score, text))
        if not ranked:
            return None
        ranked.sort(key=lambda item: item[0], reverse=True)
        return ranked[0][1]

    def _role_anchor_terms(self, target_position: str) -> list[str]:
        if self._is_ai_role(target_position):
            return ["Python", "PyTorch", "模型", "LLM", "ASR", "TTS", "WebRTC", "推理", "数据", "指标", "Agent"]
        if "前端" in target_position:
            return ["Vue", "React", "渲染", "性能", "WebRTC", "浏览器", "组件", "状态"]
        return ["Java", "Redis", "MySQL", "Netty", "RocketMQ", "Zookeeper", "Spring", "KMS", "Trace", "接口", "并发", "集群"]

    def _clean_anchor(self, text: str) -> str:
        lines = []
        for raw in text.splitlines():
            line = re.sub(r"^[\s•·●■\-]+", "", raw.strip())
            if line and not self._looks_like_heading(line):
                lines.append(line)
        return "\n".join(lines).strip()[:900]

    def _short_anchor(self, text: str, limit: int = 90) -> str:
        lines = [line for line in text.splitlines() if line.strip()]
        preferred = next((line for line in lines if "项目名称" in line or "系统" in line or "实习" in line or "Shopee" in line), lines[0] if lines else text)
        preferred = re.sub(r"^[\s•·●■\-]+", "", preferred).replace("项目名称：", "").strip()
        return preferred if len(preferred) <= limit else f"{preferred[:limit]}..."

    def _anchor_terms(self, anchor_project: str, resume_context: dict[str, Any]) -> list[str]:
        terms = []
        for term in [*resume_context.get("skills", []), *TECH_TERMS, "职责", "链路", "难点", "指标", "结果"]:
            if term and term.lower() in anchor_project.lower():
                terms.append(term)
        if not terms:
            terms = resume_context.get("skills", [])[:4]
        return list(dict.fromkeys([*terms, "职责", "链路", "难点", "结果"]))[:8]

    def _example_terms(self, terms: list[str]) -> str:
        examples = [term for term in terms if term not in {"职责", "链路", "难点", "结果"}][:3]
        return "、".join(examples) if examples else "项目里的核心技术"

    def _looks_like_heading(self, text: str) -> bool:
        normalized = re.sub(r"[\s【】\[\]（）():：]", "", text)
        return normalized in {"项目背景", "工作内容", "项目描述", "项目成果", "项目经历", "技术栈", "个人职责"} or bool(re.fullmatch(r"项目经历\d*", normalized))

    def _session_id(self, session: dict[str, Any]) -> str:
        for session_id, value in store.mock_sessions.items():
            if value is session:
                return session_id
        return ""

    def _keywords(self, answer: str, current_question: dict[str, Any]) -> list[str]:
        terms = [*TECH_TERMS, *current_question.get("expected_terms", [])]
        hits = [term for term in terms if term and term.lower() in answer.lower()]
        chinese_terms = re.findall(r"[\u4e00-\u9fff]{2,8}", answer)
        for term in chinese_terms:
            if term in {"项目", "系统", "负责", "实现", "使用", "然后", "这个", "因为"}:
                continue
            if len(hits) >= 10:
                break
            hits.append(term)
        return list(dict.fromkeys(hits))[:10]

    def _depth_score(self, answer: str, keywords: list[str], current_question: dict[str, Any]) -> int:
        stripped = answer.strip()
        question_type = current_question.get("question_type", "")
        length_score = min(24, len(stripped) // 6)
        structure_words = self._structure_words(question_type)
        structure_score = sum(5 for word in structure_words if word in stripped)
        quantified = 10 if re.search(r"\d|%|倍|毫秒|QPS|TPS|O\(|fps|万", stripped, flags=re.IGNORECASE) else 0
        expected_hits = self._expected_hit_count(stripped, current_question)
        expected_score = min(24, expected_hits * 6)
        keyword_score = min(12, len(keywords) * 3)
        richness_terms = ["背景", "方案", "难点", "结果", "职责", "取舍", "性能", "提升", "解释", "定位", "验证", "边界"]
        richness_count = sum(1 for term in richness_terms if term in stripped)
        richness_score = min(12, richness_count * 3)
        base = 22 if question_type.startswith("project") else 24
        return max(0, min(100, base + length_score + structure_score + quantified + expected_score + keyword_score + richness_score))

    def _structure_words(self, question_type: str) -> list[str]:
        if question_type.startswith("project"):
            return ["背景", "职责", "模块", "链路", "方案", "难点", "指标", "结果", "验证", "取舍"]
        if question_type == "algorithm":
            return ["数据结构", "复杂度", "边界", "输入", "输出", "哈希", "堆", "排序"]
        if question_type == "system_design":
            return ["瓶颈", "扩展", "缓存", "队列", "监控", "降级", "一致性", "取舍"]
        if question_type == "behavioral":
            return ["背景", "任务", "行动", "结果", "沟通", "复盘"]
        return ["定义", "场景", "步骤", "风险", "边界", "验证"]

    def _expected_hit_count(self, answer: str, current_question: dict[str, Any]) -> int:
        lowered = answer.lower()
        return sum(1 for term in current_question.get("expected_terms", []) if term and term.lower() in lowered)

    def _missing_expected_terms(self, answer: str, current_question: dict[str, Any]) -> list[str]:
        lowered = answer.lower()
        return [term for term in current_question.get("expected_terms", []) if term and term.lower() not in lowered][:3]

    def _pressure(self, depth_score: int, turn_count: int, mode: str) -> int:
        base = 38 + turn_count * 5
        if mode == "behavioral":
            base += 8
        if depth_score < 55:
            base += 16
        elif depth_score > 80:
            base -= 10
        return max(15, min(95, base))

    def _feedback_text(self, state: InterviewGraphState) -> str:
        current = state["session"].get("current_question", {})
        missing = self._missing_expected_terms(state.get("answer", ""), current)
        if state["depth_score"] < 55:
            if missing:
                return f"回答还偏浅，尤其缺少对「{missing[0]}」的说明。建议补充定义、适用场景、风险和判断依据。"
            return "回答还偏浅，需要补充场景、关键步骤、风险和可验证结果。"
        if state["depth_score"] < 78:
            return "回答基本完整，但还可以把关键决策、边界情况和量化结果说得更清楚。"
        return "回答信息量较好，已经覆盖关键点，我会切到下一阶段考察。"

    def _probing_reason(self, state: InterviewGraphState) -> str:
        current = state["session"].get("current_question", {})
        missing = self._missing_expected_terms(state.get("answer", ""), current)
        if missing:
            return f"当前题目还缺少关键点：{', '.join(missing)}。"
        if state["depth_score"] < 55:
            return "回答深度不足，缺少具体步骤或可验证结果。"
        return "回答中出现了可继续深挖的技术线索。"

    def _updated_scores(self, current: dict[str, int], state: InterviewGraphState) -> dict[str, int]:
        score = state["depth_score"]
        question_type = state["session"].get("current_question", {}).get("question_type", "role_core")
        mapping = {
            "project_warmup": "项目表达",
            "project_basic": "项目表达",
            "project_tech_basic": "岗位基础",
            "project_implementation": "项目表达",
            "project_deep": "项目表达",
            "project": "项目表达",
            "role_core": "岗位基础",
            "foundation": "计算机基础",
            "algorithm": "算法思维",
            "system_design": "系统设计",
            "open": "临场应变",
            "behavioral": "临场应变",
        }
        key = mapping.get(question_type, "岗位基础")
        next_scores = dict(current)
        next_scores[key] = round((next_scores.get(key, 50) + score) / 2)
        if question_type in {"open", "behavioral"}:
            next_scores["临场应变"] = round((next_scores.get("临场应变", 50) + max(20, 100 - state["pressure_level"] + score // 3)) / 2)
        return next_scores

    def _final_report(self, session: dict[str, Any], state: InterviewGraphState, include_current: bool = True) -> dict[str, Any]:
        scores = self._updated_scores(session["skill_scores"], state) if include_current else dict(session["skill_scores"])
        average = round(sum(scores.values()) / len(scores))
        weak = [name for name, score in scores.items() if score < 65] or ["量化表达"]
        covered = "项目暖场、项目基础、项目实现、项目深挖、岗位基础、算法思维、系统设计和行为抗压"
        if not session.get("has_resume_context"):
            covered = "岗位认知、岗位基础、计算机基础、算法思维、系统设计、开放问题和行为抗压"
        return {
            "summary": f"本轮模拟面试综合表现 {average} 分。已覆盖{covered}。",
            "dimension_scores": scores,
            "strengths": ["能够围绕问题展开回答", "具备继续追问的技术线索"],
            "weaknesses": weak[:3],
            "practice_suggestions": [
                "把项目题按“背景-职责-链路-难点-指标-复盘”结构复盘",
                "基础题按“定义-场景-风险-边界-验证”结构复盘",
                "针对低分维度刷 3 道专项练习题",
            ],
        }

    def _is_ai_role(self, target_position: str) -> bool:
        return any(word in target_position for word in ["AI", "算法", "机器学习", "深度学习", "自然语言", "视觉"])

    def _normalize_mode(self, mode: str) -> str:
        return mode if mode in MODE_LABELS else "project_deep_dive"

    def _clamp(self, value: Any, fallback: int = 0) -> int:
        try:
            return max(0, min(100, int(round(float(value)))))
        except (TypeError, ValueError):
            return fallback

    def _strings(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()][:8]
