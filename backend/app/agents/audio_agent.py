from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from app.agents.question_agent import QuestionGenerationAgent
from app.core.database import review_db
from app.core.storage import store
from app.models import (
    AbilityReport,
    AcousticPoint,
    CapturedInterviewQuestion,
    RagDiagnosis,
    ReviewReport,
    ReviewStatus,
    TaskRecord,
    TaskStatus,
    TranscriptSegment,
)
from app.services.audio_processing import AudioChunkingError, AudioChunkingService
from app.services.learning_rag import LearningRagService
from app.services.xfyun_clients import XfyunSpeechClient, XfyunSparkClient


class InterviewAudioAnalysisAgent:
    def __init__(
        self,
        speech_client: XfyunSpeechClient | None = None,
        spark_client: XfyunSparkClient | None = None,
        question_agent: QuestionGenerationAgent | None = None,
        chunker: AudioChunkingService | None = None,
        rag: LearningRagService | None = None,
    ) -> None:
        self.speech_client = speech_client or XfyunSpeechClient()
        self.spark_client = spark_client or XfyunSparkClient()
        self.question_agent = question_agent or QuestionGenerationAgent()
        self.chunker = chunker or AudioChunkingService()
        self.rag = rag or LearningRagService()

    def analyze(self, task: TaskRecord, audio_path: Path, user_id: str) -> TaskRecord:
        try:
            self._update_task(task, user_id, TaskStatus.running, 10, "chunking", "正在转码并切分长音频。")
            try:
                chunks = self.chunker.split(audio_path)
            except AudioChunkingError as exc:
                task.error_detail = str(exc)
                chunks = []

            self._update_task(task, user_id, TaskStatus.running, 35, "transcribing", "正在调用讯飞语音听写。")
            chunk_texts: list[tuple[str, int, int]] = []
            for chunk in chunks:
                result = self.speech_client.transcribe_chunk(chunk.path)
                text = result.data.get("text", "") if result.ok and result.data else ""
                if text:
                    chunk_texts.append((text, chunk.start_ms, chunk.end_ms))

            if not chunk_texts:
                chunk_texts = [(self._fallback_transcript(audio_path.name), 0, 60000)]

            segments = self._segments_from_chunks(chunk_texts)
            transcript = "\n".join(f"{segment.speaker}：{segment.text}" for segment in segments)

            self._update_task(task, user_id, TaskStatus.running, 62, "rag_diagnosis", "正在检索面试宝典并定位漏点。")
            captured = self._capture_questions(segments)
            diagnostics = self._diagnose_segments(segments)
            acoustic_points = self._acoustic_points(segments)
            report = self._build_report(task, user_id, audio_path.name, transcript, segments, diagnostics, captured, acoustic_points)

            if self._has_real_dialogue(segments):
                self._update_task(task, user_id, TaskStatus.running, 84, "spark_review", "正在调用 Spark X1.5 生成复盘摘要。")
                self._merge_spark_review(report)

            store.reports.setdefault(user_id, []).append(
                AbilityReport(
                    user_id=user_id,
                    transcript=report.transcript,
                    extracted_questions=[item.title for item in report.captured_questions],
                    dimension_scores=report.dimension_scores,
                    summary=report.summary,
                    growth_suggestions=report.growth_suggestions,
                )
            )
            review_db.save_review(report)
            task.review_report_id = report.id
            task.result = {"review_id": report.id, "captured_questions": [item.title for item in report.captured_questions]}
            self._update_task(task, user_id, TaskStatus.completed, 100, "ready_for_review", "录音复盘完成，等待讲师复核。")
            return task
        except Exception as exc:  # pragma: no cover - defensive background task guard
            task.error_detail = str(exc)
            self._update_task(task, user_id, TaskStatus.failed, task.progress, "failed", "录音复盘失败。")
            return task

    def _update_task(
        self,
        task: TaskRecord,
        user_id: str,
        status: TaskStatus,
        progress: int,
        stage: str,
        message: str,
    ) -> None:
        task.status = status
        task.progress = max(0, min(100, progress))
        task.stage = stage
        task.message = message
        store.tasks[task.id] = task
        review_db.save_task(task, user_id)

    def _segments_from_chunks(self, chunks: list[tuple[str, int, int]]) -> list[TranscriptSegment]:
        segments: list[TranscriptSegment] = []
        for text, start_ms, end_ms in chunks:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if not lines:
                lines = re.split(r"(?<=[。？！?])", text)
            cursor = start_ms
            duration = max(1, end_ms - start_ms)
            slice_ms = max(1500, duration // max(1, len(lines)))
            fallback_chunk = any(self._is_system_notice(line) for line in lines) or self._is_system_notice(text)
            for index, line in enumerate(lines):
                speaker, content = self._split_speaker(line, len(segments))
                if not content:
                    continue
                segment = TranscriptSegment(
                    speaker=speaker,
                    text=content,
                    start_ms=cursor,
                    end_ms=min(end_ms, cursor + slice_ms),
                    confidence=0.45 if speaker == "system" else 0.55 if fallback_chunk else 0.86,
                )
                segments.append(segment)
                cursor = segment.end_ms
        return segments

    def _split_speaker(self, line: str, index: int) -> tuple[str, str]:
        normalized = line.strip()
        if self._is_system_notice(normalized):
            return "system", normalized
        for delimiter in ["：", ":"]:
            if delimiter in normalized:
                speaker, content = normalized.split(delimiter, 1)
                if "系统" in speaker or speaker.lower().startswith("system"):
                    return "system", content.strip()
                if "面试官" in speaker or speaker.lower().startswith("q"):
                    return "interviewer", content.strip()
                if "学生" in speaker or "我" in speaker or speaker.lower().startswith("a"):
                    return "student", content.strip()
        if normalized.endswith(("？", "?")) or index % 2 == 0:
            return "interviewer", normalized
        return "student", normalized

    def _capture_questions(self, segments: list[TranscriptSegment]) -> list[CapturedInterviewQuestion]:
        captured: list[CapturedInterviewQuestion] = []
        for segment in segments:
            if not self._should_diagnose_segment(segment) or not self._is_professional_question(segment.text):
                continue
            question = self.question_agent.add_real_interview_question(segment.text)
            segment.captured_question_id = question.id
            segment.captured_question_title = question.title
            captured.append(
                CapturedInterviewQuestion(
                    question_id=question.id,
                    title=question.title,
                    skill_tags=question.skill_tags,
                    source_segment_id=segment.id,
                )
            )
        return captured

    def _diagnose_segments(self, segments: list[TranscriptSegment]) -> list[RagDiagnosis]:
        diagnostics: list[RagDiagnosis] = []
        for index, segment in enumerate(segments):
            if not self._should_diagnose_segment(segment):
                continue
            answer = self._next_student_answer(segments, index)
            chunks = self.rag.search(segment.text, top_k=3)
            ideal = self._ideal_points(segment.text, chunks)
            hit_points = [point for point in ideal if point.lower() in answer.lower()]
            missing_points = [point for point in ideal if point not in hit_points]
            diagnostics.append(
                RagDiagnosis(
                    segment_id=segment.id,
                    question=segment.text,
                    ideal_outline=ideal,
                    hit_points=hit_points,
                    missing_points=missing_points,
                    correction_advice="建议补齐红色漏点，并用项目例子说明取舍。" if missing_points else "回答覆盖了主要踩分点。",
                )
            )
        return diagnostics

    def _ideal_points(self, question: str, chunks) -> list[str]:
        text = f"{question}\n" + "\n".join(chunk.text for chunk in chunks)
        candidates = ["业务场景", "技术方案", "难点处理", "量化结果"]
        if "Redis" in text or "缓存" in text:
            candidates = ["随机过期时间", "互斥锁", "限流降级", "缓存预热"]
        elif "Spring" in text or "自动装配" in text:
            candidates = ["starter", "条件装配", "配置绑定", "自动配置类"]
        elif "索引" in text or "SQL" in text:
            candidates = ["选择性", "最左前缀", "回表", "执行计划"]
        return candidates

    def _next_student_answer(self, segments: list[TranscriptSegment], question_index: int) -> str:
        for segment in segments[question_index + 1 :]:
            if segment.speaker == "student":
                return segment.text
        return ""

    def _acoustic_points(self, segments: list[TranscriptSegment]) -> list[AcousticPoint]:
        points: list[AcousticPoint] = []
        for segment in segments:
            if segment.speaker != "student":
                continue
            duration_seconds = max((segment.end_ms - segment.start_ms) / 1000, 1)
            filler_count = sum(segment.text.count(word) for word in ["嗯", "啊", "这个", "然后"])
            speech_rate = round(len(segment.text) / duration_seconds * 60, 1)
            emotion = "hesitant" if filler_count >= 2 or speech_rate < 120 else "steady"
            points.append(AcousticPoint(time_ms=segment.start_ms, speech_rate=speech_rate, filler_count=filler_count, emotion=emotion))
        return points

    def _build_report(
        self,
        task: TaskRecord,
        user_id: str,
        filename: str,
        transcript: str,
        segments: list[TranscriptSegment],
        diagnostics: list[RagDiagnosis],
        captured: list[CapturedInterviewQuestion],
        acoustic_points: list[AcousticPoint],
    ) -> ReviewReport:
        missing_count = sum(len(item.missing_points) for item in diagnostics)
        filler_count = sum(point.filler_count for point in acoustic_points)
        has_real_dialogue = self._has_real_dialogue(segments)
        accuracy = 45 if not has_real_dialogue else max(45, 88 - missing_count * 6)
        fluency = 45 if not has_real_dialogue else max(45, 90 - filler_count * 8)
        confidence = 45 if not has_real_dialogue else max(45, round(sum(point.speech_rate for point in acoustic_points) / max(len(acoustic_points), 1) / 2))
        summary = (
            "复盘控制室已就绪，期待您的真实录音上传分析。"
            if not has_real_dialogue
            else "系统已完成逐句转写、真题捕获和 RAG 漏点诊断。请讲师重点复核知识漏点与关键片段。"
        )
        suggestions = (
            ["上传真实面试录音后，可查看逐句复盘与讲师批注。", "建议优先复盘项目介绍、技术追问和回答结构。", "可结合右侧诊断面板补齐知识点与表达证据。"]
            if not has_real_dialogue
            else ["用 STAR 结构补齐回答证据。", "对遗漏知识点准备 30 秒补充说明。", "减少“嗯、啊、然后”等冗余词。"]
        )
        return ReviewReport(
            task_id=task.id,
            owner_user_id=user_id,
            status=ReviewStatus.ready_for_review,
            audio_filename=filename,
            transcript=transcript,
            segments=segments,
            rag_diagnostics=diagnostics,
            captured_questions=captured,
            acoustic_points=acoustic_points,
            dimension_scores={"准确度": accuracy, "流畅度": fluency, "自信度": min(95, confidence)},
            summary=summary,
            growth_suggestions=suggestions,
        )

    def _merge_spark_review(self, report: ReviewReport) -> None:
        result = self.spark_client.analyze_review(
            {
                "transcript": report.transcript,
                "dimension_scores": report.dimension_scores,
                "rag_diagnostics": [item.model_dump(mode="json") for item in report.rag_diagnostics],
                "schema": {"summary": "string", "growth_suggestions": ["string"], "dimension_scores": {"准确度": 0}},
            }
        )
        if not result.ok or not result.data:
            return
        if isinstance(result.data.get("summary"), str):
            report.summary = result.data["summary"]
        if isinstance(result.data.get("growth_suggestions"), list):
            report.growth_suggestions = [str(item) for item in result.data["growth_suggestions"][:6]]
        if isinstance(result.data.get("dimension_scores"), dict):
            for key, value in result.data["dimension_scores"].items():
                try:
                    report.dimension_scores[str(key)] = max(0, min(100, int(value)))
                except (TypeError, ValueError):
                    continue

    def _is_professional_question(self, text: str) -> bool:
        if any(word in text for word in ["家住", "哪里人", "薪资", "婚"]):
            return False
        return any(
            word in text
            for word in ["项目", "Spring", "Redis", "数据库", "索引", "算法", "模型", "缓存", "并发", "架构", "自动装配"]
        )

    def _is_system_notice(self, text: str) -> bool:
        return any(
            marker in text
            for marker in [
                "语音识别待接入",
                "音频切分失败",
                "已接收录音文件",
                "当前为预分析",
                "期待您的真实录音上传分析",
            ]
        )

    def _should_diagnose_segment(self, segment: TranscriptSegment) -> bool:
        return segment.speaker == "interviewer" and segment.confidence >= 0.6 and not self._is_system_notice(segment.text)

    def _has_real_dialogue(self, segments: list[TranscriptSegment]) -> bool:
        return any(
            segment.speaker in {"interviewer", "student"} and segment.confidence >= 0.6 and not self._is_system_notice(segment.text)
            for segment in segments
        )

    def _fallback_transcript(self, filename: str) -> str:
        return (
            "系统：复盘控制室已准备就绪，期待您的真实录音上传分析。\n"
            "面试官：请介绍你最有代表性的项目，并说明你的职责、关键技术和最终结果。\n"
            "学生：我做过一个智能面试助手项目，负责后端 Agent 调度、简历解析和任务状态流转。\n"
            "面试官：如果这个系统要支持大量录音异步复盘，你会如何设计任务队列、失败重试和进度通知？\n"
            "学生：我会把上传、切片、转写、RAG 诊断拆成阶段任务，记录进度和错误详情，并在前端轮询或推送完成通知。\n"
            "面试官：说说你对 Spring Boot 自动装配的理解，以及如何排查自动配置没有生效的问题。\n"
            "学生：主要是通过 starter、自动配置类和条件注解加载 Bean。排查时我会看依赖、配置属性、条件匹配报告和日志。"
        )
