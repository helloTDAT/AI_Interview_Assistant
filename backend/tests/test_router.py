from app.agents.router_agent import RouterAgent


def test_router_classifies_learning_request():
    response = RouterAgent().route("u1", "请根据我的简历生成练习题", "后端开发工程师")
    assert response.intent == "learning_resource"


def test_router_classifies_mock_interview_request():
    response = RouterAgent().route("u1", "开始模拟面试")
    assert response.intent == "mock_interview"
