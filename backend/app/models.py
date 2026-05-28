from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class UserRole(str, Enum):
    student = "student"
    teacher = "teacher"
    admin = "admin"


class ReviewStatus(str, Enum):
    processing = "processing"
    ready_for_review = "ready_for_review"
    reviewed = "reviewed"
    failed = "failed"


class QuestionSource(str, Enum):
    real_interview = "real_interview"
    handbook = "handbook"
    generated = "generated"
    open_source = "open_source"


class ResumeFileKind(str, Enum):
    pdf = "pdf"
    docx = "docx"
    image = "image"
    unsupported = "unsupported"


class ResumeProfile(BaseModel):
    candidate_name: str | None = None
    contact: str | None = None
    education: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    internships: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certificates: list[str] = Field(default_factory=list)
    target_position: str | None = None
    raw_text: str = ""
    parse_confidence: float = 0.0
    source_kind: ResumeFileKind = ResumeFileKind.unsupported
    warnings: list[str] = Field(default_factory=list)


class ResumeAnalysisReport(BaseModel):
    profile: ResumeProfile
    quality_score: int
    dimension_scores: dict[str, int]
    forbidden_words: list[str]
    template_similarity_score: int
    job_fit: dict[str, Any]
    recommendations: list[str]
    analysis_engine: str = "rules"
    llm_error: str | None = None
    jd_diagnosis: dict[str, Any] = Field(default_factory=dict)
    interview_risks: list[dict[str, Any]] = Field(default_factory=list)
    logic_gaps: list[dict[str, Any]] = Field(default_factory=list)
    reading_experience: dict[str, Any] = Field(default_factory=dict)
    star_optimizations: list[dict[str, Any]] = Field(default_factory=list)
    needs_user_confirmation: bool = False


class ChatRequest(BaseModel):
    user_id: str = "demo-user"
    message: str
    target_position: str | None = None


class ChatResponse(BaseModel):
    intent: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class UserPublic(BaseModel):
    id: str
    username: str
    role: UserRole
    display_name: str


class AuthResponse(BaseModel):
    token: str
    user: UserPublic


class MockInterviewStartRequest(BaseModel):
    user_id: str = "demo-user"
    target_position: str = "后端开发工程师"
    mode: str = "project_deep_dive"


class MockInterviewMessageRequest(BaseModel):
    session_id: str
    answer: str


class MockInterviewFinishRequest(BaseModel):
    session_id: str
    reason: str = "user_requested"


class MockInterviewResponse(BaseModel):
    session_id: str
    question: str
    feedback: str | None = None
    round_index: int
    round_total: int = 8
    finished: bool = False
    state: str = "Greeting"
    mode: str = "project_deep_dive"
    question_type: str = "project"
    phase_label: str | None = None
    anchor_project: str | None = None
    difficulty_level: str | None = None
    question_intent: str | None = None
    probing_reason: str | None = None
    detected_keywords: list[str] = Field(default_factory=list)
    pressure_level: int = 35
    answer_depth_score: int = 0
    skill_scores: dict[str, int] = Field(default_factory=dict)
    reverse_question_prompt: str | None = None
    final_report: dict[str, Any] | None = None


class Question(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    answer_reference: str = ""
    source: QuestionSource = QuestionSource.generated
    position: str | None = None
    skill_tags: list[str] = Field(default_factory=list)
    difficulty: str = "medium"
    occurrence_count: int = 1
    source_url: str | None = None
    license: str | None = None
    badge: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LearningFeedRequest(BaseModel):
    user_id: str = "demo-user"
    target_position: str = "后端开发工程师"
    limit: int = 8
    last_answer_score: int | None = None


class LearningAnswerRequest(BaseModel):
    user_id: str = "demo-user"
    question_id: str
    answer_text: str = ""
    answer_mode: str = "text"
    target_position: str | None = None


class LearningAnswerFeedback(BaseModel):
    question_id: str
    score: int
    passed: bool
    highlights: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    senior_answer: str = ""
    next_difficulty: str = "medium"
    source: str = "rules"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LearningInsightNode(BaseModel):
    skill: str
    mastery: int
    attempts: int = 0
    status: str = "locked"


class RagChunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    title: str = ""
    repo: str = ""
    path: str = ""
    license: str = ""
    source_url: str = ""
    skill_tags: list[str] = Field(default_factory=list)
    embedding: list[float] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TaskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: TaskStatus = TaskStatus.pending
    kind: str
    message: str = ""
    result: dict[str, Any] | None = None
    progress: int = 0
    stage: str = "pending"
    review_report_id: str | None = None
    error_detail: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AbilityReport(BaseModel):
    user_id: str
    transcript: str
    extracted_questions: list[str]
    dimension_scores: dict[str, int]
    summary: str
    growth_suggestions: list[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TranscriptSegment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    speaker: str
    text: str
    start_ms: int = 0
    end_ms: int = 0
    confidence: float = 0.8
    captured_question_id: str | None = None
    captured_question_title: str | None = None
    ai_score: int | None = None
    teacher_score: int | None = None


class RagDiagnosis(BaseModel):
    segment_id: str
    question: str
    ideal_outline: list[str] = Field(default_factory=list)
    hit_points: list[str] = Field(default_factory=list)
    missing_points: list[str] = Field(default_factory=list)
    correction_advice: str = ""


class ReviewAnnotation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    review_id: str
    segment_id: str
    author_id: str
    author_name: str
    body: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AcousticPoint(BaseModel):
    time_ms: int
    speech_rate: float
    filler_count: int = 0
    emotion: str = "steady"


class CapturedInterviewQuestion(BaseModel):
    question_id: str
    title: str
    skill_tags: list[str] = Field(default_factory=list)
    source_segment_id: str
    duplicate_of: str | None = None


class ReviewReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    owner_user_id: str
    status: ReviewStatus = ReviewStatus.processing
    audio_filename: str = ""
    transcript: str = ""
    segments: list[TranscriptSegment] = Field(default_factory=list)
    rag_diagnostics: list[RagDiagnosis] = Field(default_factory=list)
    annotations: list[ReviewAnnotation] = Field(default_factory=list)
    captured_questions: list[CapturedInterviewQuestion] = Field(default_factory=list)
    acoustic_points: list[AcousticPoint] = Field(default_factory=list)
    dimension_scores: dict[str, int] = Field(default_factory=dict)
    summary: str = ""
    growth_suggestions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewAnnotationCreate(BaseModel):
    segment_id: str
    body: str


class SegmentUpdateRequest(BaseModel):
    text: str | None = None
    speaker: str | None = None
    captured_question_title: str | None = None
    teacher_score: int | None = None
