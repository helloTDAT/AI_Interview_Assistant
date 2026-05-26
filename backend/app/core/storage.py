from app.models import AbilityReport, Question, TaskRecord


class InMemoryStore:
    def __init__(self) -> None:
        self.resume_reports: dict[str, dict] = {}
        self.mock_sessions: dict[str, dict] = {}
        self.tasks: dict[str, TaskRecord] = {}
        self.questions: dict[str, Question] = {}
        self.reports: dict[str, list[AbilityReport]] = {}
        self.seed_questions()

    def seed_questions(self) -> None:
        seeds = [
            Question(
                title="请介绍一个你最有代表性的项目，并说明你的职责。",
                answer_reference="建议按背景、目标、行动、结果展开，突出个人贡献和量化结果。",
                position="软件开发",
                skill_tags=["项目经历", "表达能力"],
                source="handbook",
            ),
            Question(
                title="你如何定位并解决一次线上故障？",
                answer_reference="应覆盖现象、排查路径、根因、修复、复盘和预防。",
                position="后端开发工程师",
                skill_tags=["后端", "问题排查"],
                source="handbook",
            ),
            Question(
                title="请解释数据库索引的作用和使用注意事项。",
                answer_reference="应提到查询加速、维护成本、选择性、联合索引最左前缀等。",
                position="后端开发工程师",
                skill_tags=["数据库"],
                source="handbook",
            ),
        ]
        for question in seeds:
            self.questions[question.id] = question


store = InMemoryStore()
