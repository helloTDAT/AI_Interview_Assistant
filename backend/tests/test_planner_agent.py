from fastapi.testclient import TestClient

from app.core.storage import store
from app.main import app


client = TestClient(app)


def test_agent_plan_generates_trace_and_learning_feed():
    store.resume_reports["planner-user"] = {
        "profile": {
            "skills": ["Python", "RAG"],
            "projects": ["智能面试助手：负责 RAG 检索和题目生成"],
            "raw_text": "智能面试助手：负责 RAG 检索和题目生成",
        }
    }

    response = client.post(
        "/agent/plan",
        json={"user_id": "planner-user", "message": "请根据我的简历规划 AI 面试练习计划", "target_position": "AI算法工程师"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["steps"]
    assert any(trace["tool_name"] == "get_resume_profile" and trace["status"] == "completed" for trace in body["traces"])
    assert any(trace["tool_name"] == "generate_learning_feed" for trace in body["traces"])
    assert body["data"]["questions"]
    assert "Agent 已规划" in body["final_message"]


def test_chat_uses_planner_for_cross_task_request_without_resume():
    store.resume_reports.pop("no-resume-user", None)

    response = client.post(
        "/chat",
        json={"user_id": "no-resume-user", "message": "请根据我的简历规划后端面试练习计划", "target_position": "后端开发工程师"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "agent_plan"
    assert any(trace["tool_name"] == "get_resume_profile" and trace["status"] == "fallback" for trace in body["data"]["traces"])
    assert "不会伪造简历内容" in str(body["data"]["traces"])
