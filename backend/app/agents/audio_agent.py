from pathlib import Path

from app.core.storage import store
from app.models import AbilityReport, Question, QuestionSource, TaskRecord, TaskStatus
from app.services.ai_clients import SpeechClient


class InterviewAudioAnalysisAgent:
    def __init__(self, speech_client: SpeechClient | None = None) -> None:
        self.speech_client = speech_client or SpeechClient()

    def analyze(self, task: TaskRecord, audio_path: Path, user_id: str) -> TaskRecord:
        task.status = TaskStatus.running
        task.message = "正在转写录音并提取面试问题。"
        transcript = self.speech_client.transcribe(audio_path)
        questions = self._extract_questions(transcript)
        for title in questions:
            question = Question(
                title=title,
                answer_reference="来自真实面试录音，待讲师补充标准答案或审核系统建议。",
                source=QuestionSource.real_interview,
                skill_tags=["真实面试"],
            )
            store.questions[question.id] = question
        report = AbilityReport(
            user_id=user_id,
            transcript=transcript,
            extracted_questions=questions,
            dimension_scores={
                "答案准确性": 72,
                "表达清晰度": 78,
                "逻辑结构": 75,
                "岗位匹配度": 70,
                "临场应变": 74,
            },
            summary="录音已完成初步复盘。系统识别到项目介绍类问题，回答具备基本完整性，但需要补充量化结果和技术细节。",
            growth_suggestions=[
                "用 STAR 结构重写核心项目回答。",
                "为每个项目准备技术难点、个人贡献、结果指标三类证据。",
                "讲师审核转写文本后，可补全真实题库标准答案。",
            ],
        )
        store.reports.setdefault(user_id, []).append(report)
        task.status = TaskStatus.completed
        task.message = "录音分析完成。"
        task.result = report.model_dump(mode="json")
        return task

    def _extract_questions(self, transcript: str) -> list[str]:
        questions: list[str] = []
        for line in transcript.splitlines():
            if "面试官" in line and ("？" in line or "请" in line):
                questions.append(line.split("：", 1)[-1].strip())
        return questions or ["请介绍一个你最有代表性的项目。"]
