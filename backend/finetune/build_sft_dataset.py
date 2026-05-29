from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.storage import store
from app.services.learning_rag import LearningRagService


SYSTEM_PROMPT = "你是智能面试助手的垂类 Agent，只基于给定资料输出清楚、具体、可执行的中文回答。"


def build_records(limit: int = 200, vector_dir: str | None = None) -> list[dict[str, Any]]:
    LearningRagService(vector_dir=vector_dir).ensure_seeded()
    records: list[dict[str, Any]] = []
    for question in list(store.questions.values())[:limit]:
        title = question.title[:60]
        user = f"请生成一道面向{question.position or '目标岗位'}的练习题，技能标签：{', '.join(question.skill_tags)}。"
        assistant = json.dumps(
            {
                "title": title,
                "prompt": question.prompt or "请结合场景、方案、难点和结果作答。",
                "answer_reference": question.answer_reference,
                "skill_tags": question.skill_tags,
                "difficulty": question.difficulty,
            },
            ensure_ascii=False,
        )
        records.append(_chat_record(user, assistant))

        feedback_user = f"题目：{title}\n候选人回答：我会先说明背景，再讲方案、风险和结果。请评分并给出改进建议。"
        feedback_assistant = json.dumps(
            {
                "score": 72,
                "highlights": ["回答具备基本结构。"],
                "improvements": ["补充真实项目证据、关键取舍和量化结果。"],
                "senior_answer": question.answer_reference or "先澄清场景，再说明方案、边界和验证方式。",
            },
            ensure_ascii=False,
        )
        records.append(_chat_record(feedback_user, feedback_assistant))

    for chunk in list(store.rag_chunks.values())[:limit]:
        user = f"基于面试宝典片段总结 3 个踩分点：\n{chunk.text[:700]}"
        assistant = json.dumps(
            {
                "ideal_outline": _outline_from_text(chunk.text),
                "correction_advice": "回答时先给结论，再结合项目场景说明取舍、边界和验证结果。",
                "source": {"repo": chunk.repo, "path": chunk.path, "license": chunk.license},
            },
            ensure_ascii=False,
        )
        records.append(_chat_record(user, assistant))

    records.extend(_resume_demo_records())
    return records[:limit]


def write_jsonl(records: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _chat_record(user: str, assistant: str) -> dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }


def _outline_from_text(text: str) -> list[str]:
    candidates = ["业务场景", "技术方案", "难点处理", "量化结果"]
    if "Redis" in text or "缓存" in text:
        candidates = ["随机过期时间", "互斥锁", "限流降级", "缓存预热"]
    elif "索引" in text or "SQL" in text:
        candidates = ["执行计划", "索引选择性", "最左前缀", "回表"]
    elif "Agent" in text or "RAG" in text:
        candidates = ["任务规划", "工具调用", "上下文注入", "答案溯源"]
    return candidates


def _resume_demo_records() -> list[dict[str, Any]]:
    user = "目标岗位：AI算法工程师\n简历片段：参与智能面试助手，负责 RAG 检索、题目生成和答题反馈。请输出简历优化 JSON。"
    assistant = json.dumps(
        {
            "quality_score": 82,
            "recommendations": ["补充模型或检索效果指标。", "说明你负责的模块边界和线上验证方式。"],
            "job_fit": {"target_position": "AI算法工程师", "matched_skills": ["RAG", "题目生成"], "missing_skills": ["模型评估"]},
        },
        ensure_ascii=False,
    )
    return [_chat_record(user, assistant)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SFT JSONL for interview-assistant LoRA demos.")
    parser.add_argument("--output", default="backend/finetune/data/interview_sft.jsonl")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    output = Path(args.output)
    records = build_records(limit=args.limit)
    write_jsonl(records, output)
    print(f"Wrote {len(records)} SFT records to {output}")


if __name__ == "__main__":
    main()
