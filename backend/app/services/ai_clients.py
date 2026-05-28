from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.models import Question, ResumeProfile


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
    """ChatAnywhere adapter with deterministic fallbacks for local/test flows."""

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        embedding_model: str | None = None,
        timeout_seconds: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self.provider = provider if provider is not None else settings.llm_provider
        self.api_key = api_key if api_key is not None else settings.chatanywhere_api_key
        self.base_url = (base_url if base_url is not None else settings.chatanywhere_base_url).rstrip("/")
        self.model = model if model is not None else settings.chatanywhere_model
        self.embedding_model = (
            embedding_model if embedding_model is not None else settings.chatanywhere_embedding_model
        )
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds
        self.max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens

    def classify_intent(self, message: str) -> str:
        text = message.lower()
        if any(word in text for word in ["练习题", "学习", "题库", "推荐题", "刷题", "错题"]):
            return "learning_resource"
        if any(word in text for word in ["简历", "resume", "cv"]):
            return "resume_analysis"
        if any(word in text for word in ["模拟面试", "开始面试", "mock interview"]):
            return "mock_interview"
        if any(word in text for word in ["录音", "复盘", "真实面试", "audio"]):
            return "audio_analysis"
        return "general_chat"

    def summarize(self, text: str, purpose: str) -> str:
        compact = " ".join(text.split())
        if len(compact) > 180:
            compact = compact[:180] + "..."
        return f"{purpose}: {compact}" if compact else f"{purpose}: 暂无足够文本。"

    def chat_json(self, messages: list[dict[str, str]], *, temperature: float = 0.2) -> LLMCallResult:
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

    def embed_texts(self, texts: list[str]) -> LLMCallResult:
        if self.provider != "chatanywhere":
            return LLMCallResult(ok=False, error=f"unsupported provider: {self.provider}")
        if not self.api_key:
            return LLMCallResult(ok=False, error="chatanywhere api key is not configured")
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self.embedding_model, "input": texts},
                )
            response.raise_for_status()
            body = response.json()
            embeddings = [item["embedding"] for item in body["data"]]
            return LLMCallResult(ok=True, data={"embeddings": embeddings})
        except httpx.HTTPStatusError as exc:
            return LLMCallResult(ok=False, error=f"embedding http {exc.response.status_code}")
        except httpx.TimeoutException:
            return LLMCallResult(ok=False, error="embedding request timed out")
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            return LLMCallResult(ok=False, error=f"embedding response invalid: {exc}")

    def generate_learning_questions(
        self,
        *,
        target_position: str,
        skills: list[str],
        rag_context: list[str],
        count: int,
        difficulty: str,
    ) -> LLMCallResult:
        return self.chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "你是面向大学生求职的面试题生成 Agent。只返回合法 JSON。"
                        "不要编造用户不存在的经历；可以围绕技能生成可练习的问题。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": "生成结构化面试练习题",
                            "target_position": target_position,
                            "skills": skills,
                            "difficulty": difficulty,
                            "count": count,
                            "rag_context": rag_context,
                            "schema": {
                                "questions": [
                                    {
                                        "title": "题目",
                                        "answer_reference": "参考回答思路",
                                        "skill_tags": ["技能"],
                                        "difficulty": difficulty,
                                    }
                                ]
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0.35,
        )

    def evaluate_learning_answer(self, question: Question, answer_text: str, rag_context: list[str]) -> LLMCallResult:
        return self.chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "你是严谨但鼓励式的 AI 面试考官。只返回合法 JSON。"
                        "评分必须基于题目、用户答案和资料上下文，不能假装用户说过不存在的信息。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question.title,
                            "answer_reference": question.answer_reference,
                            "skill_tags": question.skill_tags,
                            "candidate_answer": answer_text,
                            "rag_context": rag_context,
                            "schema": {
                                "score": "0-100整数",
                                "highlights": ["回答亮点"],
                                "improvements": ["改进建议"],
                                "senior_answer": "资深工程师参考思路",
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0.2,
        )

    def generate_mock_interview_turn(self, payload: dict[str, Any]) -> LLMCallResult:
        return self.chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "你是严谨但有压迫感的 AI 技术面试官。只返回合法 JSON。"
                        "你需要根据候选人的目标岗位、简历线索、面试模式和上一轮回答，决定继续深挖、切换新题、进入反向提问或结束总结。"
                        "不要编造候选人没有说过的经历；如果信息不足，明确用追问确认。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            **payload,
                            "schema": {
                                "decision": "probe | new_question | reverse_qa | closing",
                                "question": "下一句面试官问题",
                                "feedback": "对上一轮回答的简短反馈",
                                "probing_reason": "为什么追问或切题",
                                "detected_keywords": ["关键词"],
                                "answer_depth_score": "0-100 整数",
                                "pressure_level": "0-100 整数",
                                "skill_scores": {"专业深度": 0, "项目表达": 0, "临场应变": 0},
                                "final_report": {
                                    "summary": "结束时填写",
                                    "strengths": ["优势"],
                                    "weaknesses": ["薄弱项"],
                                    "practice_suggestions": ["练习建议"],
                                },
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0.35,
        )

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
                        "你是面向大学生求职场景的简历评估专家。只返回合法 JSON。"
                        "不要编造简历中不存在的经历、项目、指标、论文、奖项或技能。"
                        "不要把“项目背景”“工作内容”“项目成果”“技术栈”等章节标题当作项目、风险点或 STAR before。"
                        "interview_risks 和 star_optimizations 必须基于具体经历句，不能只因某个词出现就判断有问题。"
                        "如果 parse_confidence 较低，必须明确这是预分析。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "请生成简历评估 JSON，字段包含 quality_score, dimension_scores, job_fit, "
                        "recommendations, jd_diagnosis, interview_risks, logic_gaps, "
                        "reading_experience, star_optimizations。输入："
                        f"{json.dumps(prompt, ensure_ascii=False)}"
                    ),
                },
            ]
        )

    def local_embedding(self, text: str, dims: int = 64) -> list[float]:
        vector = [0.0] * dims
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % dims
            sign = 1 if digest[2] % 2 == 0 else -1
            vector[index] += sign * (1 + len(token) / 10)
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [round(value / norm, 6) for value in vector]

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
    """OCR adapter placeholder."""

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
