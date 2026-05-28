from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile

from app.agents.audio_agent import InterviewAudioAnalysisAgent
from app.agents.mock_interview_agent import MockInterviewAgent
from app.agents.question_agent import QuestionGenerationAgent
from app.agents.resume_agent import ResumeEvaluationAgent
from app.agents.router_agent import RouterAgent
from app.core.config import settings
from app.core.database import review_db
from app.core.storage import store
from app.models import (
    AuthLoginRequest,
    AuthResponse,
    ChatRequest,
    ChatResponse,
    LearningAnswerRequest,
    LearningFeedRequest,
    MockInterviewFinishRequest,
    MockInterviewMessageRequest,
    MockInterviewResponse,
    MockInterviewStartRequest,
    Question,
    ReviewAnnotation,
    ReviewAnnotationCreate,
    SegmentUpdateRequest,
    TaskRecord,
    UserPublic,
    UserRole,
)

router = APIRouter()
router_agent = RouterAgent()
resume_agent = ResumeEvaluationAgent()
mock_agent = MockInterviewAgent()
question_agent = QuestionGenerationAgent()
audio_agent = InterviewAudioAnalysisAgent(question_agent=question_agent)


def _save_upload(file: UploadFile) -> Path:
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix
    path = upload_dir / f"{uuid4()}{suffix}"
    with path.open("wb") as handle:
        handle.write(file.file.read())
    return path


def _token_from_header(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def optional_user(authorization: str | None = Header(default=None)) -> UserPublic | None:
    token = _token_from_header(authorization)
    return review_db.user_for_token(token) if token else None


def current_user(authorization: str | None = Header(default=None)) -> UserPublic:
    user = optional_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录。")
    return user


def require_teacher(user: UserPublic = Depends(current_user)) -> UserPublic:
    if user.role not in {UserRole.teacher, UserRole.admin}:
        raise HTTPException(status_code=403, detail="需要讲师或管理员权限。")
    return user


def _can_view_review(user: UserPublic, owner_user_id: str) -> bool:
    return user.role in {UserRole.teacher, UserRole.admin} or user.id == owner_user_id


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: AuthLoginRequest) -> AuthResponse:
    result = review_db.login(payload.username, payload.password)
    if not result:
        raise HTTPException(status_code=401, detail="用户名或密码错误。")
    token, user = result
    return AuthResponse(token=token, user=user)


@router.post("/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> dict[str, bool]:
    token = _token_from_header(authorization)
    if token:
        review_db.logout(token)
    return {"ok": True}


@router.get("/auth/me")
def me(user: UserPublic = Depends(current_user)) -> dict:
    return {"user": user.model_dump(mode="json")}


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
    return mock_agent.start(payload.user_id, payload.target_position, payload.mode)


@router.post("/interviews/mock/message", response_model=MockInterviewResponse)
def send_mock_answer(payload: MockInterviewMessageRequest) -> MockInterviewResponse:
    if payload.session_id not in store.mock_sessions:
        raise HTTPException(status_code=404, detail="模拟面试会话不存在。")
    return mock_agent.answer(payload.session_id, payload.answer)


@router.post("/interviews/mock/finish", response_model=MockInterviewResponse)
def finish_mock_interview(payload: MockInterviewFinishRequest) -> MockInterviewResponse:
    if payload.session_id not in store.mock_sessions:
        raise HTTPException(status_code=404, detail="模拟面试会话不存在。")
    return mock_agent.finish(payload.session_id, payload.reason)


@router.post("/interviews/audio", response_model=TaskRecord)
def upload_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Form("demo-user"),
    user: UserPublic | None = Depends(optional_user),
) -> TaskRecord:
    owner_id = user.id if user else user_id
    path = _save_upload(file)
    task = TaskRecord(
        kind="interview_audio_analysis",
        message="录音已接收，正在呼叫音频解析 Agent 进行声纹分离与知识点比对。",
        progress=5,
        stage="queued",
    )
    store.tasks[task.id] = task
    review_db.save_task(task, owner_id)
    background_tasks.add_task(audio_agent.analyze, task, path, owner_id)
    return task


@router.get("/tasks")
def list_tasks(user: UserPublic = Depends(current_user)) -> dict:
    return {"tasks": [task.model_dump(mode="json") for task in review_db.list_tasks(user)]}


@router.get("/tasks/{task_id}", response_model=TaskRecord)
def get_task(task_id: str) -> TaskRecord:
    task = store.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在。")
    return task


@router.get("/reports/{user_id}")
def get_reports(user_id: str):
    return {"reports": [report.model_dump(mode="json") for report in store.reports.get(user_id, [])]}


@router.get("/reviews/{review_id}")
def get_review(review_id: str, user: UserPublic = Depends(current_user)) -> dict:
    review = review_db.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="复盘报告不存在。")
    if not _can_view_review(user, review.owner_user_id):
        raise HTTPException(status_code=403, detail="无权查看该复盘。")
    return {"review": review.model_dump(mode="json")}


@router.post("/reviews/{review_id}/annotations")
def create_annotation(
    review_id: str,
    payload: ReviewAnnotationCreate,
    user: UserPublic = Depends(require_teacher),
) -> dict:
    review = review_db.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="复盘报告不存在。")
    if not any(segment.id == payload.segment_id for segment in review.segments):
        raise HTTPException(status_code=404, detail="转写句子不存在。")
    annotation = ReviewAnnotation(
        review_id=review_id,
        segment_id=payload.segment_id,
        author_id=user.id,
        author_name=user.display_name,
        body=payload.body,
    )
    review.annotations.append(annotation)
    review_db.add_annotation(annotation)
    review_db.save_review(review)
    return {"annotation": annotation.model_dump(mode="json")}


@router.put("/reviews/{review_id}/segments/{segment_id}")
def update_segment(
    review_id: str,
    segment_id: str,
    payload: SegmentUpdateRequest,
    user: UserPublic = Depends(require_teacher),
) -> dict:
    review = review_db.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="复盘报告不存在。")
    segment = next((item for item in review.segments if item.id == segment_id), None)
    if not segment:
        raise HTTPException(status_code=404, detail="转写句子不存在。")
    if payload.text is not None:
        segment.text = payload.text
    if payload.speaker is not None:
        segment.speaker = payload.speaker
    if payload.captured_question_title is not None:
        segment.captured_question_title = payload.captured_question_title
    if payload.teacher_score is not None:
        segment.teacher_score = max(0, min(100, payload.teacher_score))
    review_db.save_review(review)
    return {"segment": segment.model_dump(mode="json")}


@router.get("/questions")
def list_questions() -> dict:
    return {"questions": [q.model_dump(mode="json") for q in store.questions.values()]}


@router.post("/questions", response_model=Question)
def create_question(question: Question) -> Question:
    store.questions[question.id] = question
    question_agent.rag.add_question(question)
    return question


@router.put("/questions/{question_id}", response_model=Question)
def update_question(question_id: str, question: Question) -> Question:
    if question_id not in store.questions:
        raise HTTPException(status_code=404, detail="题目不存在。")
    question.id = question_id
    store.questions[question_id] = question
    question_agent.rag.add_question(question)
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


@router.post("/learning/feed")
def learning_feed(payload: LearningFeedRequest) -> dict:
    report = store.resume_reports.get(payload.user_id)
    profile = report["profile"] if report else None
    result = question_agent.feed(
        payload.user_id,
        profile,
        payload.target_position,
        payload.limit,
        payload.last_answer_score,
    )
    return {
        "questions": [q.model_dump(mode="json") for q in result["questions"]],
        "insights": [node.model_dump(mode="json") for node in result["insights"]],
        "rag_status": result["rag_status"],
    }


@router.post("/learning/answers")
def submit_learning_answer(payload: LearningAnswerRequest) -> dict:
    try:
        feedback = question_agent.answer(payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="题目不存在。") from None
    return {"feedback": feedback.model_dump(mode="json")}


@router.get("/learning/mistakes/{user_id}")
def learning_mistakes(user_id: str) -> dict:
    return {"mistakes": question_agent.mistakes(user_id)}


@router.get("/learning/insights/{user_id}")
def learning_insights(user_id: str) -> dict:
    return {"insights": [node.model_dump(mode="json") for node in question_agent.insights(user_id)]}
