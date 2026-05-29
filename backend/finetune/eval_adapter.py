from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import Question, ResumeFileKind, ResumeProfile
from app.services.ai_clients import LLMClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Run fixed probes against the optional local fine-tuned adapter.")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--adapter-path", default="")
    args = parser.parse_args()

    client = LLMClient(api_key="", model=args.model_path)
    client.local_adapter.enabled = True
    client.local_adapter.model_path = args.model_path
    client.local_adapter.adapter_path = args.adapter_path or None

    probes = {
        "learning_questions": client.generate_learning_questions(
            target_position="AI算法工程师",
            skills=["Python", "RAG", "PyTorch"],
            rag_context=["RAG 包含切片、召回、重排、上下文注入和答案溯源。"],
            count=2,
            difficulty="medium",
        ),
        "answer_feedback": client.evaluate_learning_answer(
            Question(title="RAG 检索效果不好怎么排查？", skill_tags=["RAG"], answer_reference="说明召回、重排、上下文和评估。"),
            "我会看切片、召回和模型回答。",
            ["需要覆盖召回率、重排和答案溯源。"],
        ),
        "resume_report": client.analyze_resume_report(
            ResumeProfile(
                skills=["Python", "RAG"],
                projects=["智能面试助手：负责本地 RAG 和题目生成。"],
                raw_text="智能面试助手：负责本地 RAG 和题目生成。",
                source_kind=ResumeFileKind.docx,
                parse_confidence=0.9,
            ),
            "AI算法工程师",
        ),
    }
    print(json.dumps({name: asdict(result) for name, result in probes.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
