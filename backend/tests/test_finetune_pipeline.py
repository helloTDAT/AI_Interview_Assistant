import json

from finetune.build_sft_dataset import build_records, write_jsonl
from app.services.ai_clients import LLMClient


def test_sft_dataset_builder_outputs_chatml_without_secrets(tmp_path):
    records = build_records(limit=8, vector_dir=str(tmp_path / "rag"))
    output = tmp_path / "interview_sft.jsonl"
    write_jsonl(records, output)

    lines = output.read_text(encoding="utf-8").splitlines()
    assert lines
    first = json.loads(lines[0])
    assert [message["role"] for message in first["messages"]] == ["system", "user", "assistant"]
    payload = "\n".join(lines)
    assert "CHATANYWHERE_API_KEY" not in payload
    assert "XFYUN_API_KEY" not in payload


def test_local_finetuned_adapter_is_disabled_by_default():
    client = LLMClient(api_key="")

    result = client.local_adapter.chat_json(task="probe", messages=[{"role": "user", "content": "return json"}])

    assert result.ok is False
    assert "disabled" in result.error
