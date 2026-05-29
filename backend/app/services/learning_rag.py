from __future__ import annotations

import json
import math
import re
from collections import Counter
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

LOCAL_SEED_REPO = "internal/local-rag-seed"
LOCAL_SEED_MARKDOWN = """
# Redis 缓存高频题

Redis 缓存雪崩需要关注随机过期时间、热点 key 预热、互斥锁、限流降级和缓存重建保护。
缓存穿透可以使用布隆过滤器、空值缓存、参数校验和访问频率限制。
缓存一致性常见方案包括先更新数据库再删除缓存、延迟双删、消息队列重试和最终一致性监控。

## MySQL 与 SQL

慢查询排查通常从执行计划、索引选择性、联合索引最左前缀、回表、数据量、排序和分页策略入手。
事务问题需要说明 ACID、隔离级别、幻读、MVCC、锁粒度和死锁排查。

## Java 并发与 Spring

Java 并发题应覆盖线程安全、锁、线程池、阻塞队列、可见性、原子性和线上观测指标。
Spring Boot 自动装配需要提到 starter、条件装配、自动配置类、配置绑定和 SPI/Factories 机制。

## 算法与系统设计

Top K 可以用小根堆、快排分区、桶计数或流式近似算法，需要说明复杂度和边界。
LRU 需要哈希表加双向链表，重点说明 O(1) 查询、更新、淘汰和并发安全。
系统设计题需要先澄清规模、读写比例、延迟目标，再说明服务拆分、缓存、队列、幂等、降级和可观测性。

## Agent 与 RAG

一个完整 Agent 通常包含任务规划、工具调用、记忆/上下文、状态管理、反思评估和安全边界。
RAG 检索增强一般包含文档切片、向量或关键词索引、召回、重排、上下文注入和答案溯源。
""".strip()


class LearningRagService:
    """Local-first RAG store for fast foreground retrieval."""

    def __init__(
        self,
        llm: LLMClient | None = None,
        vector_dir: str | None = None,
        embedding_client: XfyunEmbeddingClient | None = None,
        use_cloud_embedding: bool = False,
    ) -> None:
        self.llm = llm or LLMClient()
        self.embedding_client = embedding_client or XfyunEmbeddingClient()
        self.use_cloud_embedding = use_cloud_embedding
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
        text = f"{question.title}\n{question.prompt}\n{question.answer_reference}"
        existing = self._find_existing("internal-question-bank", question.id)
        if existing:
            existing.text = text
            existing.title = question.title
            existing.skill_tags = question.skill_tags
            existing.embedding = self._embed_one(text)
            self.persist()
            return existing
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
        if repo not in ALLOWED_REPOS and repo != LOCAL_SEED_REPO:
            raise ValueError("source repo or license is not in the approved open-source whitelist")
        if license_value not in ALLOWED_LICENSES and license_value != "internal":
            raise ValueError("source repo or license is not in the approved open-source whitelist")

        chunks = []
        for index, text in enumerate(self._split_markdown(markdown)):
            title = self._title_from_chunk(text) or f"{repo} chunk {index + 1}"
            chunk_path = f"{path}#{index + 1}"
            existing = self._find_existing(repo, chunk_path)
            if existing:
                chunks.append(existing)
                continue
            chunk = RagChunk(
                text=text,
                title=title,
                repo=repo,
                path=chunk_path,
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
        self.ensure_seeded()
        if not store.rag_chunks:
            return []
        tags = {tag.lower() for tag in (skill_tags or [])}
        query_tokens = self._tokenize(query)
        query_embedding = self._embed_one(query)
        all_doc_tokens = [self._tokenize(chunk.text) for chunk in store.rag_chunks.values()]
        doc_count = max(1, len(all_doc_tokens))
        document_frequency = Counter(token for tokens in all_doc_tokens for token in set(tokens))
        average_length = sum(len(tokens) for tokens in all_doc_tokens) / doc_count if all_doc_tokens else 1.0
        scored: list[tuple[float, RagChunk]] = []
        for chunk in store.rag_chunks.values():
            chunk_tokens = self._tokenize(f"{chunk.title}\n{chunk.text}")
            score = self._bm25(query_tokens, chunk_tokens, document_frequency, doc_count, average_length)
            score += self._cosine(query_embedding, chunk.embedding) * 0.35
            title_hits = sum(1 for token in query_tokens if token and token in chunk.title.lower())
            score += title_hits * 0.4
            if tags and any(tag.lower() in tags for tag in chunk.skill_tags):
                score += 1.2
            scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]

    def _embed_one(self, text: str) -> list[float]:
        if not self.use_cloud_embedding:
            return self.llm.local_embedding(text)
        xfyun_result = self.embedding_client.embed_texts([text])
        if xfyun_result.ok and xfyun_result.data and xfyun_result.data.get("embeddings"):
            return [float(value) for value in xfyun_result.data["embeddings"][0]]
        result = self.llm.embed_texts([text])
        if result.ok and result.data and result.data.get("embeddings"):
            return [float(value) for value in result.data["embeddings"][0]]
        return self.llm.local_embedding(text)

    def ensure_seeded(self) -> None:
        if not store.rag_chunks:
            self.import_markdown(
                repo=LOCAL_SEED_REPO,
                path="seed/interview-handbook.md",
                markdown=LOCAL_SEED_MARKDOWN,
                license_name="internal",
                source_url="local://seed/interview-handbook.md",
            )
        for question in list(store.questions.values())[:50]:
            if not self._find_existing("internal-question-bank", question.id):
                self.add_question(question)

    def _find_existing(self, repo: str, path: str) -> RagChunk | None:
        for chunk in store.rag_chunks.values():
            if chunk.repo == repo and chunk.path == path:
                return chunk
        return None

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
        known = [
            "Java",
            "Spring",
            "Redis",
            "MySQL",
            "SQL",
            "并发",
            "JVM",
            "Python",
            "机器学习",
            "算法",
            "项目经历",
            "Agent",
            "RAG",
            "系统设计",
            "缓存",
            "事务",
        ]
        return [tag for tag in known if tag.lower() in text.lower()]

    def _tokenize(self, text: str) -> list[str]:
        lowered = text.lower()
        latin = re.findall(r"[a-z0-9_+#.-]+", lowered)
        chinese_terms = [
            "缓存",
            "雪崩",
            "穿透",
            "一致性",
            "索引",
            "事务",
            "并发",
            "线程",
            "算法",
            "系统设计",
            "自动装配",
            "向量",
            "检索",
            "切片",
            "重排",
            "项目",
            "架构",
            "队列",
            "限流",
            "降级",
            "幂等",
            "复杂度",
        ]
        chinese = [term for term in chinese_terms if term in lowered]
        chars = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)
        return [*latin, *chinese, *chars]

    def _bm25(
        self,
        query_tokens: list[str],
        doc_tokens: list[str],
        document_frequency: Counter,
        doc_count: int,
        average_length: float,
    ) -> float:
        if not query_tokens or not doc_tokens:
            return 0.0
        frequencies = Counter(doc_tokens)
        k1 = 1.5
        b = 0.75
        doc_length = len(doc_tokens)
        score = 0.0
        for token in set(query_tokens):
            term_frequency = frequencies[token]
            if term_frequency <= 0:
                continue
            df = document_frequency.get(token, 0)
            idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
            denominator = term_frequency + k1 * (1 - b + b * doc_length / max(average_length, 1.0))
            score += idf * (term_frequency * (k1 + 1)) / denominator
        return score

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
