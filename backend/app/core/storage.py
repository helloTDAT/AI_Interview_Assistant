from app.models import AbilityReport, LearningAnswerFeedback, Question, QuestionSource, RagChunk, TaskRecord


class InMemoryStore:
    def __init__(self) -> None:
        self.resume_reports: dict[str, dict] = {}
        self.mock_sessions: dict[str, dict] = {}
        self.tasks: dict[str, TaskRecord] = {}
        self.questions: dict[str, Question] = {}
        self.reports: dict[str, list[AbilityReport]] = {}
        self.learning_answers: dict[str, list[LearningAnswerFeedback]] = {}
        self.rag_chunks: dict[str, RagChunk] = {}
        self.seed_questions()

    def seed_questions(self) -> None:
        seeds = [
            Question(
                title="请介绍一个你最有代表性的项目，并说明你的职责。",
                answer_reference="建议按 STAR 展开：背景、目标、行动、结果，突出个人贡献和量化结果。",
                position="软件开发",
                skill_tags=["项目经历", "表达能力"],
                source=QuestionSource.handbook,
                difficulty="easy",
            ),
            Question(
                title="你如何定位并解决一次线上故障？",
                answer_reference="回答应覆盖现象、排查路径、根因、修复、复盘和预防机制。",
                position="后端开发工程师",
                skill_tags=["后端", "问题排查"],
                source=QuestionSource.handbook,
                difficulty="medium",
            ),
            Question(
                title="请解释数据库索引的作用和使用注意事项。",
                answer_reference="应提到查询加速、维护成本、选择性、联合索引最左前缀、回表和慢查询分析。",
                position="后端开发工程师",
                skill_tags=["数据库"],
                source=QuestionSource.handbook,
                difficulty="medium",
            ),
            Question(
                title="如果系统需要从单体演进到高并发架构，你会如何拆分服务并保证数据一致性？",
                answer_reference="可从瓶颈定位、服务边界、缓存、消息队列、幂等、事务一致性和可观测性展开。",
                position="Java 开发工程师",
                skill_tags=["Java", "Spring Boot", "架构设计", "并发"],
                source=QuestionSource.open_source,
                difficulty="hard",
                license="Apache-2.0",
                source_url="https://github.com/Snailclimb/JavaGuide",
            ),
        ]
        for question in seeds:
            self.questions[question.id] = question


store = InMemoryStore()
