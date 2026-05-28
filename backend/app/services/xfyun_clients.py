from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urlencode, urlparse

import httpx

from app.core.config import settings
from app.services.ai_clients import LLMCallResult


class XfyunSparkClient:
    def __init__(self, api_password: str | None = None, base_url: str | None = None, model: str | None = None) -> None:
        self.api_password = api_password if api_password is not None else settings.xfyun_spark_api_password
        self.base_url = (base_url or settings.xfyun_spark_base_url).rstrip("/")
        self.model = model or settings.xfyun_spark_model

    def analyze_review(self, payload: dict) -> LLMCallResult:
        if not self.api_password:
            return LLMCallResult(ok=False, error="xfyun spark api password is not configured")
        try:
            with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_password}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "你是专业面试复盘 Agent。只返回合法 JSON，不要编造用户没有说过的内容。",
                            },
                            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                        ],
                        "temperature": 0.2,
                    },
                )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return LLMCallResult(ok=True, data=json.loads(content), raw_text=content)
        except httpx.HTTPStatusError as exc:
            return LLMCallResult(ok=False, error=f"xfyun spark http {exc.response.status_code}")
        except Exception as exc:  # pragma: no cover - defensive for vendor schema variants
            return LLMCallResult(ok=False, error=f"xfyun spark response invalid: {exc}")


class XfyunEmbeddingClient:
    def __init__(self, api_key: str | None = None, api_secret: str | None = None, url: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.xfyun_api_key
        self.api_secret = api_secret if api_secret is not None else settings.xfyun_api_secret
        self.url = url or settings.xfyun_embedding_url

    def embed_texts(self, texts: list[str]) -> LLMCallResult:
        if not self.api_key or not self.api_secret:
            return LLMCallResult(ok=False, error="xfyun embedding credentials are not configured")
        try:
            with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
                response = client.post(
                    self.url,
                    headers=self._signed_headers("POST", self.url),
                    json={"input": texts},
                )
            response.raise_for_status()
            body = response.json()
            data = body.get("data") or []
            embeddings = data.get("embeddings") if isinstance(data, dict) else data
            return LLMCallResult(ok=True, data={"embeddings": embeddings})
        except httpx.HTTPStatusError as exc:
            return LLMCallResult(ok=False, error=f"xfyun embedding http {exc.response.status_code}")
        except Exception as exc:  # pragma: no cover
            return LLMCallResult(ok=False, error=f"xfyun embedding response invalid: {exc}")

    def _signed_headers(self, method: str, url: str) -> dict[str, str]:
        parsed = urlparse(url)
        date = format_datetime(datetime.utcnow())
        signature_origin = f"host: {parsed.netloc}\ndate: {date}\n{method} {parsed.path or '/'} HTTP/1.1"
        signature = base64.b64encode(
            hmac.new(self.api_secret.encode("utf-8"), signature_origin.encode("utf-8"), hashlib.sha256).digest()
        ).decode("utf-8")
        authorization_origin = (
            f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", '
            f'signature="{signature}"'
        )
        return {
            "Authorization": base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8"),
            "Date": date,
            "Host": parsed.netloc,
            "Content-Type": "application/json",
        }


class XfyunSpeechClient:
    def __init__(
        self,
        app_id: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        url: str | None = None,
    ) -> None:
        self.app_id = app_id if app_id is not None else settings.xfyun_app_id
        self.api_key = api_key if api_key is not None else settings.xfyun_api_key
        self.api_secret = api_secret if api_secret is not None else settings.xfyun_api_secret
        self.url = url or settings.xfyun_iat_url

    def transcribe_chunk(self, audio_path: Path) -> LLMCallResult:
        if not self.app_id or not self.api_key or not self.api_secret:
            return LLMCallResult(ok=False, error="xfyun speech credentials are not configured")
        try:
            from websockets.sync.client import connect
        except ImportError as exc:
            return LLMCallResult(ok=False, error=f"websockets is not installed: {exc}")

        try:
            with connect(self._signed_url()) as websocket:
                audio = audio_path.read_bytes()
                websocket.send(
                    json.dumps(
                        {
                            "common": {"app_id": self.app_id},
                            "business": {"language": "zh_cn", "domain": "iat", "accent": "mandarin", "dwa": "wpgs"},
                            "data": {
                                "status": 2,
                                "format": "audio/L16;rate=16000",
                                "encoding": "raw",
                                "audio": base64.b64encode(audio).decode("utf-8"),
                            },
                        }
                    )
                )
                chunks: list[str] = []
                while True:
                    message = json.loads(websocket.recv())
                    if message.get("code") != 0:
                        return LLMCallResult(ok=False, error=f"xfyun speech code {message.get('code')}")
                    words = message.get("data", {}).get("result", {}).get("ws", [])
                    chunks.extend(candidate.get("w", "") for item in words for candidate in item.get("cw", []))
                    if message.get("data", {}).get("status") == 2:
                        break
                return LLMCallResult(ok=True, data={"text": "".join(chunks)})
        except Exception as exc:  # pragma: no cover - network path
            return LLMCallResult(ok=False, error=f"xfyun speech failed: {exc}")

    def _signed_url(self) -> str:
        parsed = urlparse(self.url)
        date = format_datetime(datetime.utcnow())
        signature_origin = f"host: {parsed.netloc}\ndate: {date}\nGET {parsed.path} HTTP/1.1"
        signature_sha = hmac.new(
            self.api_secret.encode("utf-8"), signature_origin.encode("utf-8"), digestmod=hashlib.sha256
        ).digest()
        signature = base64.b64encode(signature_sha).decode("utf-8")
        authorization_origin = (
            f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", '
            f'signature="{signature}"'
        )
        query = urlencode(
            {
                "authorization": base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8"),
                "date": date,
                "host": parsed.netloc,
            }
        )
        return f"{self.url}?{query}"
