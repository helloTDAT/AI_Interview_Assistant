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


class QuestionSource(str, Enum):
    real_interview = "real_interview"
    handbook = "handbook"
    generated = "generated"


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


class MockInterviewStartRequest(BaseModel):
    user_id: str = "demo-user"
    target_position: str = "后端开发工程师"


class MockInterviewMessageRequest(BaseModel):
    session_id: str
    answer: str


class MockInterviewResponse(BaseModel):
    session_id: str
    question: str
    feedback: str | None = None
    round_index: int
    finished: bool = False


class Question(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    answer_reference: str = ""
    source: QuestionSource = QuestionSource.generated
    position: str | None = None
    skill_tags: list[str] = Field(default_factory=list)
    difficulty: str = "medium"
    occurrence_count: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TaskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: TaskStatus = TaskStatus.pending
    kind: str
    message: str = ""
    result: dict[str, Any] | None = None
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
