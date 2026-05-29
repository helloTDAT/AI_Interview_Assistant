from typing import Any

from app.models import AbilityReport, LearningAnswerFeedback, Question, QuestionSource, RagChunk, ResumeProfile, TaskRecord


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


def get_active_resume_report(user_id: str) -> dict[str, Any] | None:
    report = store.resume_reports.get(user_id)
    return report if isinstance(report, dict) else None


def get_active_resume_profile(user_id: str) -> ResumeProfile | dict[str, Any] | None:
    report = get_active_resume_report(user_id)
    return report.get("profile") if report else None


def summarize_active_resume(user_id: str) -> dict[str, Any]:
    report = get_active_resume_report(user_id)
    if not report:
        return {"available": False}
    profile = report.get("profile") or {}
    if isinstance(profile, ResumeProfile):
        skills = profile.skills
        projects = profile.projects
        internships = profile.internships
        confidence = profile.parse_confidence
        target = profile.target_position
    else:
        skills = [str(skill) for skill in profile.get("skills", [])]
        projects = [str(item) for item in profile.get("projects", [])]
        internships = [str(item) for item in profile.get("internships", [])]
        confidence = float(profile.get("parse_confidence") or 0)
        target = profile.get("target_position")
    job_fit = report.get("job_fit") or {}
    target_position = job_fit.get("target_position") or target or "目标岗位未填写"
    quality_score = report.get("quality_score")
    return {
        "available": True,
        "target_position": target_position,
        "skills": skills[:8],
        "project_count": len(projects),
        "internship_count": len(internships),
        "parse_confidence": confidence,
        "quality_score": quality_score,
        "needs_user_confirmation": bool(report.get("needs_user_confirmation") or confidence < 0.6),
    }
