from app.agents.question_agent import QuestionGenerationAgent
from app.core.storage import store
from app.models import Question, QuestionSource
from app.services.ai_clients import LLMCallResult, LLMClient
from app.services.learning_rag import LearningRagService


class DisabledEmbedding:
    def __init__(self):
        self.calls = 0

    def embed_texts(self, texts):
        self.calls += 1
        return LLMCallResult(ok=False, error="disabled")


class FakeLearningLLM:
    def __init__(self, questions=None, ok=True):
        self.questions = questions or []
        self.ok = ok
        self.local = LLMClient(api_key="")

    def generate_learning_questions(self, **kwargs):
        if not self.ok:
            return LLMCallResult(ok=False, error="mock failure")
        return LLMCallResult(ok=True, data={"questions": self.questions})

    def embed_texts(self, texts):
        return LLMCallResult(ok=False, error="disabled")

    def local_embedding(self, text, dims=64):
        return self.local.local_embedding(text, dims=dims)


def make_agent(tmp_path, llm, embedding=None):
    rag = LearningRagService(llm=llm, vector_dir=str(tmp_path), embedding_client=embedding or DisabledEmbedding())
    return QuestionGenerationAgent(llm=llm, rag=rag)


def reset_learning_store():
    store.questions.clear()
    store.rag_chunks.clear()
    store.learning_answers.clear()


def test_long_question_title_is_split_into_short_title_and_prompt(tmp_path):
    reset_learning_store()
    long_title = (
        "请按 STAR（Situation, Task, Action, Result）结构，描述一次你在团队中就数据库设计或接口返回字段与前端沟通的经历。"
        "要求包含：明确沟通目标、组织沟通、遇到的分歧、解决办法和后续跟进措施。"
    )
    agent = make_agent(tmp_path, FakeLearningLLM(ok=False))

    title, prompt = agent._normalize_question_text(long_title)

    assert len(title) <= 60
    assert "要求包含" not in title
    assert "STAR" not in title
    assert prompt
    assert "沟通目标" in prompt


def test_fallback_questions_use_short_titles_and_prompts(tmp_path):
    reset_learning_store()
    agent = make_agent(tmp_path, FakeLearningLLM(ok=False))

    result = agent.feed("demo-user", {"skills": ["Redis", "MySQL", "PyTorch"]}, "后端开发工程师", limit=6)

    generated = [question for question in result["questions"] if question.source == QuestionSource.generated]
    assert generated
    assert all(len(question.title) <= 60 for question in generated)
    assert all(question.prompt for question in generated)


def test_real_interview_question_is_prioritized_when_relevant(tmp_path):
    reset_learning_store()
    store.questions["generated"] = Question(
        id="generated",
        title="Redis 缓存一致性怎么处理？",
        source=QuestionSource.generated,
        position="后端开发工程师",
        skill_tags=["Redis"],
        difficulty="medium",
    )
    store.questions["real"] = Question(
        id="real",
        title="你们线上 Redis 缓存穿透怎么兜底？",
        source=QuestionSource.real_interview,
        position="后端开发工程师",
        skill_tags=["Redis"],
        difficulty="medium",
        occurrence_count=3,
        badge="高频实战",
    )
    agent = make_agent(tmp_path, FakeLearningLLM(ok=False))

    result = agent.feed("demo-user", {"skills": ["Redis"]}, "后端开发工程师", limit=1)

    assert result["questions"][0].id == "real"


def test_feed_insights_use_resume_skills(tmp_path):
    reset_learning_store()
    agent = make_agent(tmp_path, FakeLearningLLM(ok=False))

    result = agent.feed("demo-user", {"skills": ["Redis", "MySQL"]}, "后端开发工程师", limit=4)

    insight_names = {node.skill for node in result["insights"]}
    assert {"Redis", "MySQL"}.issubset(insight_names)


def test_learning_feed_uses_local_rag_without_cloud_embedding(tmp_path):
    reset_learning_store()
    embedding = DisabledEmbedding()
    agent = make_agent(tmp_path, FakeLearningLLM(ok=False), embedding=embedding)

    result = agent.feed("demo-user", {"skills": ["Redis", "MySQL"]}, "后端开发工程师", limit=4)

    assert result["questions"]
    assert result["rag_status"]["provider"] == "local"
    assert result["rag_status"]["retrieved"] > 0
    assert result["rag_status"]["sources"]
    assert embedding.calls == 0
