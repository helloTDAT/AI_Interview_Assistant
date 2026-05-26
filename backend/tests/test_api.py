from pathlib import Path

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.services.ai_clients import LLMCallResult, LLMClient


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_image_resume(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(routes.resume_agent, "llm", LLMClient(api_key=""))
    image = tmp_path / "resume.jpg"
    image.write_bytes(b"fake image")

    with image.open("rb") as handle:
        response = client.post(
            "/files/resume",
            files={"file": ("resume.jpg", handle, "image/jpeg")},
            data={
                "user_id": "api-user",
                "target_position": "AI算法工程师",
                "user_instruction": "请重点优化项目经历。",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["source_kind"] == "image"
    assert body["needs_user_confirmation"] is True
    assert body["job_fit"]["target_position"] == "AI算法工程师"
    assert "机器学习" in body["job_fit"]["expected_skills"]
    assert any("项目经历" in item or "项目" in item for item in body["recommendations"])


def test_mock_interview_flow():
    start = client.post("/interviews/mock/start", json={"user_id": "api-user", "target_position": "后端开发工程师"})
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    answer = client.post(
        "/interviews/mock/message",
        json={"session_id": session_id, "answer": "我负责后端接口设计，使用 FastAPI 和 MySQL 完成核心模块。"},
    )
    assert answer.status_code == 200
    assert answer.json()["feedback"]


def test_upload_resume_accepts_jd_and_llm_fields(tmp_path: Path, monkeypatch):
    class FakeLLM:
        def analyze_resume_report(self, profile, target_position, user_instruction=None, job_description=None):
            assert "PyTorch" in job_description
            return LLMCallResult(
                ok=True,
                data={
                    "quality_score": 90,
                    "dimension_scores": {"专业技能": 88, "岗位匹配": 85},
                    "job_fit": {
                        "target_position": target_position,
                        "fit_score": 85,
                        "expected_skills": ["Python", "PyTorch"],
                        "matched_skills": ["Python"],
                        "missing_skills": ["PyTorch"],
                    },
                    "recommendations": ["围绕 JD 补充 PyTorch 项目证据。"],
                    "jd_diagnosis": {
                        "enabled": True,
                        "match_rate": 85,
                        "core_requirements": ["Python", "PyTorch"],
                        "matched_items": ["Python"],
                        "missing_items": ["PyTorch"],
                        "suggestions": ["补充模型训练细节。"],
                    },
                    "interview_risks": [{"question": "请解释模型训练细节。"}],
                    "logic_gaps": [],
                    "reading_experience": {"signal_to_noise_score": 80},
                    "star_optimizations": [{"before": "做项目", "after": "建议按 STAR 改写", "action_note": "补充结果"}],
                },
            )

    monkeypatch.setattr(routes.resume_agent, "llm", FakeLLM())
    resume = tmp_path / "resume.docx"
    from docx import Document

    doc = Document()
    doc.add_paragraph("张三")
    doc.add_paragraph("技能：Python SQL")
    doc.add_paragraph("项目经历：参与算法项目。")
    doc.save(str(resume))

    with resume.open("rb") as handle:
        response = client.post(
            "/files/resume",
            files={"file": ("resume.docx", handle, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={
                "user_id": "api-user",
                "target_position": "AI算法工程师",
                "user_instruction": "请重点优化项目经历",
                "job_description": "要求 Python、PyTorch、模型评估经验",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_engine"] == "llm"
    assert body["jd_diagnosis"]["missing_items"] == ["PyTorch"]
    assert body["interview_risks"][0]["question"]
    assert body["star_optimizations"][0]["after"]


def test_audio_analysis_task(tmp_path: Path):
    audio = tmp_path / "interview.wav"
    audio.write_bytes(b"fake wav")

    with audio.open("rb") as handle:
        response = client.post(
            "/interviews/audio",
            files={"file": ("interview.wav", handle, "audio/wav")},
            data={"user_id": "audio-user"},
        )

    assert response.status_code == 200
    assert response.json()["kind"] == "interview_audio_analysis"
