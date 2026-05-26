from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.agents.audio_agent import InterviewAudioAnalysisAgent
from app.agents.mock_interview_agent import MockInterviewAgent
from app.agents.question_agent import QuestionGenerationAgent
from app.agents.resume_agent import ResumeEvaluationAgent
from app.agents.router_agent import RouterAgent
from app.core.config import settings
from app.core.storage import store
from app.models import (
    ChatRequest,
    ChatResponse,
    MockInterviewMessageRequest,
    MockInterviewResponse,
    MockInterviewStartRequest,
    Question,
    TaskRecord,
)

router = APIRouter()
router_agent = RouterAgent()
resume_agent = ResumeEvaluationAgent()
mock_agent = MockInterviewAgent()
audio_agent = InterviewAudioAnalysisAgent()
question_agent = QuestionGenerationAgent()


def _save_upload(file: UploadFile) -> Path:
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix
    path = upload_dir / f"{uuid4()}{suffix}"
    with path.open("wb") as handle:
        handle.write(file.file.read())
    return path


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    return router_agent.route(payload.user_id, payload.message, payload.target_position)


@router.post("/files/resume")
def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Form("demo-user"),
    target_position: str | None = Form(None),
    user_instruction: str | None = Form(None),
    job_description: str | None = Form(None),
):
    path = _save_upload(file)
    report = resume_agent.analyze(path, target_position, user_instruction, job_description)
    store.resume_reports[user_id] = report.model_dump(mode="python")
    return report


@router.post("/interviews/mock/start", response_model=MockInterviewResponse)
def start_mock_interview(payload: MockInterviewStartRequest) -> MockInterviewResponse:
    return mock_agent.start(payload.user_id, payload.target_position)


@router.post("/interviews/mock/message", response_model=MockInterviewResponse)
def send_mock_answer(payload: MockInterviewMessageRequest) -> MockInterviewResponse:
    if payload.session_id not in store.mock_sessions:
        raise HTTPException(status_code=404, detail="模拟面试会话不存在。")
    return mock_agent.answer(payload.session_id, payload.answer)


@router.post("/interviews/audio", response_model=TaskRecord)
def upload_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Form("demo-user"),
) -> TaskRecord:
    path = _save_upload(file)
    task = TaskRecord(kind="interview_audio_analysis", message="录音分析任务已创建。")
    store.tasks[task.id] = task
    background_tasks.add_task(audio_agent.analyze, task, path, user_id)
    return task


@router.get("/tasks/{task_id}", response_model=TaskRecord)
def get_task(task_id: str) -> TaskRecord:
    task = store.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在。")
    return task


@router.get("/reports/{user_id}")
def get_reports(user_id: str):
    return {"reports": [report.model_dump(mode="json") for report in store.reports.get(user_id, [])]}


@router.get("/questions")
def list_questions() -> dict:
    return {"questions": [q.model_dump(mode="json") for q in store.questions.values()]}


@router.post("/questions", response_model=Question)
def create_question(question: Question) -> Question:
    store.questions[question.id] = question
    return question


@router.put("/questions/{question_id}", response_model=Question)
def update_question(question_id: str, question: Question) -> Question:
    if question_id not in store.questions:
        raise HTTPException(status_code=404, detail="题目不存在。")
    question.id = question_id
    store.questions[question_id] = question
    return question


@router.delete("/questions/{question_id}")
def delete_question(question_id: str) -> dict[str, bool]:
    if question_id not in store.questions:
        raise HTTPException(status_code=404, detail="题目不存在。")
    del store.questions[question_id]
    return {"deleted": True}


@router.post("/learning/questions")
def generate_learning_questions(user_id: str = Form("demo-user"), target_position: str = Form("后端开发工程师")):
    report = store.resume_reports.get(user_id)
    profile = report["profile"] if report else None
    questions = question_agent.generate_for_resume(profile, target_position)
    return {"questions": [q.model_dump(mode="json") for q in questions]}
