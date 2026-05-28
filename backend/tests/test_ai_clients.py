import pytest

from app.services.ai_clients import LLMClient


def test_llm_client_without_api_key_returns_failure():
    client = LLMClient(api_key="")

    result = client.chat_json([{"role": "user", "content": "return json"}])

    assert result.ok is False
    assert "api key" in result.error


def test_llm_client_parses_chatanywhere_json(monkeypatch):
    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": '{"quality_score": 88}'}}]}

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            assert url == "https://api.chatanywhere.tech/v1/chat/completions"
            assert headers["Authorization"] == "Bearer test-key"
            assert json["model"] == "gpt-5-mini"
            return FakeResponse()

    monkeypatch.setattr("app.services.ai_clients.httpx.Client", FakeClient)
    client = LLMClient(api_key="test-key", model="gpt-5-mini")

    result = client.chat_json([{"role": "user", "content": "return json"}])

    assert result.ok is True
    assert result.data == {"quality_score": 88}


def test_llm_client_calls_chatanywhere_embeddings(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            assert url == "https://api.chatanywhere.tech/v1/embeddings"
            assert headers["Authorization"] == "Bearer test-key"
            assert json["model"] == "text-embedding-ada-002"
            assert json["input"] == ["hello"]
            return FakeResponse()

    monkeypatch.setattr("app.services.ai_clients.httpx.Client", FakeClient)
    client = LLMClient(api_key="test-key")

    result = client.embed_texts(["hello"])

    assert result.ok is True
    assert result.data == {"embeddings": [[0.1, 0.2, 0.3]]}


def test_llm_client_rejects_non_json(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "not json"}}]}

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            return FakeResponse()

    monkeypatch.setattr("app.services.ai_clients.httpx.Client", FakeClient)
    client = LLMClient(api_key="test-key")

    result = client.chat_json([{"role": "user", "content": "return json"}])

    assert result.ok is False
    assert "invalid" in result.error
