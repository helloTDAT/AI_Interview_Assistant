from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.audio_processing import AudioChunkingError, AudioChunkingService
from app.services.xfyun_clients import XfyunEmbeddingClient, XfyunSparkClient


client = TestClient(app)


def login(username: str, password: str) -> tuple[str, dict]:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    body = response.json()
    return body["token"], body["user"]


def test_auth_roles_and_review_annotation_flow(tmp_path: Path):
    student_token, student = login("student", "student123")
    teacher_token, teacher = login("teacher", "teacher123")
    assert student["role"] == "student"
    assert teacher["role"] == "teacher"

    audio = tmp_path / "interview.wav"
    audio.write_bytes(b"fake wav")
    with audio.open("rb") as handle:
        upload = client.post(
            "/interviews/audio",
            files={"file": ("interview.wav", handle, "audio/wav")},
            headers={"Authorization": f"Bearer {student_token}"},
        )
    assert upload.status_code == 200
    task_id = upload.json()["id"]

    task = client.get(f"/tasks/{task_id}").json()
    assert task["status"] in {"completed", "failed"}
    assert task["progress"] in {100, 5}
    assert task.get("review_report_id")

    student_tasks = client.get("/tasks", headers={"Authorization": f"Bearer {student_token}"})
    assert student_tasks.status_code == 200
    assert any(item["id"] == task_id for item in student_tasks.json()["tasks"])

    review = client.get(
        f"/reviews/{task['review_report_id']}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert review.status_code == 200
    review_body = review.json()["review"]
    assert review_body["segments"]
    assert review_body["segments"][0]["speaker"] == "system"
    assert review_body["rag_diagnostics"] == []
    assert review_body["captured_questions"] == []
    assert "期待您的真实录音上传分析" in review_body["summary"]
    for leaked_word in ["预分析", "语音识别", "音频切分", "低置信"]:
        assert leaked_word not in review_body["summary"]

    segment_id = review_body["segments"][0]["id"]
    forbidden = client.post(
        f"/reviews/{review_body['id']}/annotations",
        json={"segment_id": segment_id, "body": "学生不能添加讲师批注。"},
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert forbidden.status_code == 403

    annotation = client.post(
        f"/reviews/{review_body['id']}/annotations",
        json={"segment_id": segment_id, "body": "这里可以补充项目量化结果。"},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert annotation.status_code == 200
    assert annotation.json()["annotation"]["author_name"] == "讲师 Demo"

    update = client.put(
        f"/reviews/{review_body['id']}/segments/{segment_id}",
        json={"teacher_score": 88, "speaker": "system"},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert update.status_code == 200
    assert update.json()["segment"]["teacher_score"] == 88


def test_audio_chunker_reports_missing_ffmpeg(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("app.services.audio_processing.shutil.which", lambda _: None)
    audio = tmp_path / "demo.mp3"
    audio.write_bytes(b"fake")

    with pytest.raises(AudioChunkingError) as exc:
        AudioChunkingService().split(audio)

    assert "ffmpeg" in str(exc.value)


def test_xfyun_spark_http_mock(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": '{"summary": "ok"}'}}]}

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            assert url == "https://spark-api-open.xf-yun.com/v2/chat/completions"
            assert headers["Authorization"] == "Bearer password"
            assert json["model"] == "spark-x"
            return FakeResponse()

    monkeypatch.setattr("app.services.xfyun_clients.httpx.Client", FakeClient)
    result = XfyunSparkClient(api_password="password").analyze_review({"transcript": "demo"})

    assert result.ok is True
    assert result.data == {"summary": "ok"}


def test_xfyun_embedding_mock(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [[0.1, 0.2]]}

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            assert headers["Authorization"]
            assert json["input"] == ["Redis 缓存雪崩"]
            return FakeResponse()

    monkeypatch.setattr("app.services.xfyun_clients.httpx.Client", FakeClient)
    result = XfyunEmbeddingClient(api_key="key", api_secret="secret").embed_texts(["Redis 缓存雪崩"])

    assert result.ok is True
    assert result.data == {"embeddings": [[0.1, 0.2]]}
