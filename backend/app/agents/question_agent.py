from app.core.storage import store
from app.models import Question, QuestionSource, ResumeProfile


class QuestionGenerationAgent:
    def generate_for_resume(
        self,
        profile: ResumeProfile | dict | None,
        target_position: str = "后端开发工程师",
        count: int = 5,
    ) -> list[Question]:
        skills = self._skills(profile)
        existing = [
            q
            for q in store.questions.values()
            if not q.position or target_position in q.position or any(tag in skills for tag in q.skill_tags)
        ]
        generated: list[Question] = []
        for skill in skills[:count]:
            generated.append(
                Question(
                    title=f"请结合你的经历说明你如何使用 {skill} 解决实际问题？",
                    answer_reference="建议说明场景、技术选择、实现步骤、难点处理和结果指标。",
                    source=QuestionSource.generated,
                    position=target_position,
                    skill_tags=[skill],
                )
            )
        combined = (existing + generated)[:count]
        for question in generated:
            store.questions[question.id] = question
        return combined

    def _skills(self, profile: ResumeProfile | dict | None) -> list[str]:
        if isinstance(profile, ResumeProfile):
            return profile.skills or ["项目经历", "数据库", "沟通表达"]
        if isinstance(profile, dict):
            return profile.get("skills") or ["项目经历", "数据库", "沟通表达"]
        return ["项目经历", "数据库", "沟通表达"]
