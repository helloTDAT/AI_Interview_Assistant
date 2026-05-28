from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.storage import store
from app.models import Question, QuestionSource, RagChunk
from app.services.ai_clients import LLMClient
from app.services.xfyun_clients import XfyunEmbeddingClient


ALLOWED_LICENSES = {"MIT", "Apache-2.0", "Apache 2.0", "BSD-3-Clause", "BSD-2-Clause"}
ALLOWED_REPOS = {
    "Snailclimb/JavaGuide": "Apache-2.0",
}


class LearningRagService:
    """Small persistent vector store for MVP RAG without leaking provider calls."""

    def __init__(
        self,
        llm: LLMClient | None = None,
        vector_dir: str | None = None,
        embedding_client: XfyunEmbeddingClient | None = None,
    ) -> None:
        self.llm = llm or LLMClient()
        self.embedding_client = embedding_client or XfyunEmbeddingClient()
        self.vector_dir = Path(vector_dir or settings.rag_vector_dir)
        self.vector_file = self.vector_dir / "learning_chunks.json"
        self.load()

    def load(self) -> None:
        if not self.vector_file.exists():
            return
        try:
            raw = json.loads(self.vector_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for item in raw:
            try:
                chunk = RagChunk(**item)
            except (TypeError, ValueError):
                continue
            store.rag_chunks[chunk.id] = chunk

    def persist(self) -> None:
        self.vector_dir.mkdir(parents=True, exist_ok=True)
        payload = [chunk.model_dump(mode="json") for chunk in store.rag_chunks.values()]
        self.vector_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_question(self, question: Question) -> RagChunk:
        text = f"{question.title}\n{question.answer_reference}"
        chunk = RagChunk(
            text=text,
            title=question.title,
            repo="internal-question-bank",
            path=question.id,
            license=question.license or "internal",
            source_url=question.source_url or "",
            skill_tags=question.skill_tags,
            embedding=self._embed_one(text),
        )
        store.rag_chunks[chunk.id] = chunk
        self.persist()
        return chunk

    def import_markdown(
        self,
        *,
        repo: str,
        path: str,
        markdown: str,
        license_name: str | None = None,
        source_url: str = "",
    ) -> list[RagChunk]:
        license_value = license_name or ALLOWED_REPOS.get(repo, "")
        if repo not in ALLOWED_REPOS or license_value not in ALLOWED_LICENSES:
            raise ValueError("source repo or license is not in the approved open-source whitelist")

        chunks = []
        for index, text in enumerate(self._split_markdown(markdown)):
            title = self._title_from_chunk(text) or f"{repo} chunk {index + 1}"
            chunk = RagChunk(
                text=text,
                title=title,
                repo=repo,
                path=path,
                license=license_value,
                source_url=source_url,
                skill_tags=self._infer_tags(text),
                embedding=self._embed_one(text),
            )
            store.rag_chunks[chunk.id] = chunk
            chunks.append(chunk)
        self.persist()
        return chunks

    def search(self, query: str, *, top_k: int = 5, skill_tags: list[str] | None = None) -> list[RagChunk]:
        if not store.rag_chunks:
            for question in store.questions.values():
                self.add_question(question)
        query_embedding = self._embed_one(query)
        tags = {tag.lower() for tag in (skill_tags or [])}
        scored: list[tuple[float, RagChunk]] = []
        for chunk in store.rag_chunks.values():
            score = self._cosine(query_embedding, chunk.embedding)
            if tags and any(tag.lower() in tags for tag in chunk.skill_tags):
                score += 0.12
            scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]

    def _embed_one(self, text: str) -> list[float]:
        xfyun_result = self.embedding_client.embed_texts([text])
        if xfyun_result.ok and xfyun_result.data and xfyun_result.data.get("embeddings"):
            return [float(value) for value in xfyun_result.data["embeddings"][0]]
        result = self.llm.embed_texts([text])
        if result.ok and result.data and result.data.get("embeddings"):
            return [float(value) for value in result.data["embeddings"][0]]
        return self.llm.local_embedding(text)

    def _split_markdown(self, markdown: str, max_chars: int = 900) -> list[str]:
        cleaned = re.sub(r"```.*?```", "", markdown, flags=re.DOTALL)
        sections = re.split(r"\n(?=#{1,3}\s)", cleaned)
        chunks: list[str] = []
        for section in sections:
            compact = "\n".join(line.rstrip() for line in section.splitlines()).strip()
            if not compact:
                continue
            while len(compact) > max_chars:
                chunks.append(compact[:max_chars].strip())
                compact = compact[max_chars:].strip()
            if compact:
                chunks.append(compact)
        return chunks

    def _title_from_chunk(self, text: str) -> str:
        for line in text.splitlines():
            stripped = line.strip("# ").strip()
            if stripped:
                return stripped[:80]
        return ""

    def _infer_tags(self, text: str) -> list[str]:
        known = ["Java", "Spring", "Redis", "MySQL", "SQL", "并发", "JVM", "Python", "机器学习", "算法", "项目经历"]
        return [tag for tag in known if tag.lower() in text.lower()]

    def _cosine(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        width = min(len(left), len(right))
        numerator = sum(left[index] * right[index] for index in range(width))
        left_norm = math.sqrt(sum(value * value for value in left[:width]))
        right_norm = math.sqrt(sum(value * value for value in right[:width]))
        if not left_norm or not right_norm:
            return 0.0
        return numerator / (left_norm * right_norm)
