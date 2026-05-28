import pytest

from app.services.ai_clients import LLMClient
from app.services.learning_rag import LearningRagService


def test_rag_import_keeps_license_and_source_metadata(tmp_path):
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
    service = LearningRagService(llm=LLMClient(api_key=""), vector_dir=str(tmp_path))

    with pytest.raises(ValueError):
        service.import_markdown(
            repo="unknown/repo",
            path="README.md",
            markdown="# Question",
            license_name="GPL-3.0",
            source_url="https://example.com",
        )
