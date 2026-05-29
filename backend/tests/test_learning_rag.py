import pytest

from app.core.storage import store
from app.services.ai_clients import LLMClient
from app.services.learning_rag import LearningRagService


def test_rag_import_keeps_license_and_source_metadata(tmp_path):
    store.rag_chunks.clear()
    service = LearningRagService(llm=LLMClient(api_key=""), vector_dir=str(tmp_path))

    chunks = service.import_markdown(
        repo="Snailclimb/JavaGuide",
        path="docs/java.md",
        markdown="# Java 基础\n\n请解释 JVM 和并发。\n\n## Spring\n\nSpring Boot 如何处理请求？",
        license_name="Apache-2.0",
        source_url="https://github.com/Snailclimb/JavaGuide/docs/java.md",
    )

    assert chunks
    assert chunks[0].license == "Apache-2.0"
    assert chunks[0].repo == "Snailclimb/JavaGuide"
    assert chunks[0].source_url.startswith("https://github.com/Snailclimb/JavaGuide")


def test_rag_rejects_non_whitelisted_sources(tmp_path):
    store.rag_chunks.clear()
    service = LearningRagService(llm=LLMClient(api_key=""), vector_dir=str(tmp_path))

    with pytest.raises(ValueError):
        service.import_markdown(
            repo="unknown/repo",
            path="README.md",
            markdown="# Question",
            license_name="GPL-3.0",
            source_url="https://example.com",
        )


def test_local_rag_search_hits_imported_markdown_without_cloud_embedding(tmp_path):
    store.rag_chunks.clear()
    service = LearningRagService(llm=LLMClient(api_key=""), vector_dir=str(tmp_path))
    service.import_markdown(
        repo="Snailclimb/JavaGuide",
        path="docs/redis.md",
        markdown="# Redis 缓存\n\n缓存雪崩要使用随机过期时间、互斥锁、限流降级和缓存预热。",
        license_name="Apache-2.0",
        source_url="https://github.com/Snailclimb/JavaGuide/docs/redis.md",
    )

    chunks = service.search("Redis 缓存雪崩怎么处理", top_k=1, skill_tags=["Redis"])

    assert chunks
    assert chunks[0].repo == "Snailclimb/JavaGuide"
    assert "随机过期时间" in chunks[0].text


def test_local_rag_seeds_when_empty(tmp_path):
    store.rag_chunks.clear()
    service = LearningRagService(llm=LLMClient(api_key=""), vector_dir=str(tmp_path))

    chunks = service.search("一个完整 Agent 一般包含哪些部分", top_k=2, skill_tags=["Agent"])

    assert chunks
    assert any(chunk.repo == "internal/local-rag-seed" for chunk in chunks)
