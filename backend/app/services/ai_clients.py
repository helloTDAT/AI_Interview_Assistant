from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.models import ResumeProfile


@dataclass
class OCRResult:
    text: str
    confidence: float


@dataclass
class LLMCallResult:
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    raw_text: str = ""


class LLMClient:
    """LLM adapter with deterministic local fallbacks for non-cloud flows."""

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self.provider = provider if provider is not None else settings.llm_provider
        self.api_key = api_key if api_key is not None else settings.chatanywhere_api_key
        self.base_url = (base_url if base_url is not None else settings.chatanywhere_base_url).rstrip("/")
        self.model = model if model is not None else settings.chatanywhere_model
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds
        self.max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens

    def classify_intent(self, message: str) -> str:
        text = message.lower()
        if any(word in text for word in ["练习题", "学习", "题库", "推荐题", "缁冧範棰", "瀛︿範", "棰樺簱"]):
            return "learning_resource"
        if any(word in text for word in ["简历", "resume", "cv", "绠€鍘"]):
            return "resume_analysis"
        if any(word in text for word in ["模拟面试", "开始面试", "mock interview", "妯℃嫙闈㈣瘯", "寮€濮嬫ā鎷"]):
            return "mock_interview"
        if any(word in text for word in ["录音", "复盘", "真实面试", "audio", "褰曢煶", "澶嶇洏"]):
            return "audio_analysis"
        return "general_chat"

    def summarize(self, text: str, purpose: str) -> str:
        compact = " ".join(text.split())
        if len(compact) > 180:
            compact = compact[:180] + "..."
        return f"{purpose}: {compact}" if compact else f"{purpose}: 暂无足够文本。"

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
    ) -> LLMCallResult:
        if self.provider != "chatanywhere":
            return LLMCallResult(ok=False, error=f"unsupported provider: {self.provider}")
        if not self.api_key:
            return LLMCallResult(ok=False, error="chatanywhere api key is not configured")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            return LLMCallResult(ok=True, data=self._parse_json_content(content), raw_text=content)
        except httpx.HTTPStatusError as exc:
            return LLMCallResult(ok=False, error=f"llm http {exc.response.status_code}")
        except httpx.TimeoutException:
            return LLMCallResult(ok=False, error="llm request timed out")
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return LLMCallResult(ok=False, error=f"llm response invalid: {exc}")

    def analyze_resume_report(
        self,
        profile: ResumeProfile,
        target_position: str,
        user_instruction: str | None = None,
        job_description: str | None = None,
    ) -> LLMCallResult:
        safe_text = self._clip(profile.raw_text, 9000)
        prompt = {
            "target_position": target_position,
            "user_instruction": user_instruction or "",
            "job_description": job_description or "",
            "parse_confidence": profile.parse_confidence,
            "needs_caution": profile.parse_confidence < 0.6 or bool(profile.warnings),
            "warnings": profile.warnings,
            "resume_text": safe_text,
            "known_skills": profile.skills,
            "known_projects": profile.projects,
        }
        return self.chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "你是面向大学生求职场景的简历评估专家。"
                        "只返回合法 JSON，不要返回 Markdown。"
                        "不要编造简历中不存在的经历、项目、指标、论文、奖项或技能。"
                        "当需要量化时，用“建议补充/可改写为”的语气，不要假装数字真实存在。"
                        "如果 parse_confidence 低或 needs_caution 为 true，必须明确这是预分析，并降低结论确定性。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "请根据以下输入生成多维简历评价 JSON。字段必须包含："
                        "quality_score(int 0-100), "
                        "dimension_scores(object，键包含专业技能/项目经验/岗位匹配/表达量化/教育背景/软技能), "
                        "job_fit(object，含 target_position/fit_score/expected_skills/matched_skills/missing_skills), "
                        "recommendations(array string), "
                        "jd_diagnosis(object，含 enabled/match_rate/core_requirements/matched_items/missing_items/suggestions), "
                        "interview_risks(array object，含 risk_point/question/why_it_matters/defense_tip/severity), "
                        "logic_gaps(array object，含 issue/evidence/suggestion/severity), "
                        "reading_experience(object，含 signal_to_noise_score/cliches/density_notes/suggestions), "
                        "star_optimizations(array object，含 before/after/action_note)。\n"
                        f"输入 JSON：{json.dumps(prompt, ensure_ascii=False)}"
                    ),
                },
            ]
        )

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        cleaned = content.strip()
        fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, flags=re.DOTALL)
        if fence:
            cleaned = fence.group(1)
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("top-level LLM JSON must be an object")
        return parsed

    def _clip(self, text: str, limit: int) -> str:
        compact = text.strip()
        if len(compact) <= limit:
            return compact
        return compact[:limit] + "\n[内容过长，已截断]"


class OCRClient:
    """OCR adapter placeholder.

    Production implementation should call a cloud OCR/multimodal model. The fallback
    keeps the pipeline testable and tells the frontend when human confirmation is needed.
    """

    def extract_from_image(self, path: Path) -> OCRResult:
        return OCRResult(
            text=f"[OCR待接入] 已接收图片简历：{path.name}。请接入真实 OCR 或多模态模型返回简历文字。",
            confidence=0.35,
        )

    def extract_from_pdf_pages(self, path: Path) -> OCRResult:
        return OCRResult(
            text=f"[OCR待接入] PDF 可能为扫描版：{path.name}。请接入 PDF 转图片 + OCR 流程。",
            confidence=0.3,
        )


class SpeechClient:
    """Speech-to-text adapter placeholder."""

    def transcribe(self, path: Path) -> str:
        return (
            f"[语音识别待接入] 已接收录音文件：{path.name}。\n"
            "面试官：请介绍你最有代表性的项目。\n"
            "学生：我做过一个智能面试助手项目，负责后端 Agent 调度和简历解析。"
        )
