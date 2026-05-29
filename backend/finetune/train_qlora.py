from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a lightweight QLoRA adapter for the interview assistant.")
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--data", default="backend/finetune/data/interview_sft.jsonl")
    parser.add_argument("--output", default="backend/finetune/adapters/interview-qlora")
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--max-steps", type=int, default=-1)
    args = parser.parse_args()

    try:
        from datasets import load_dataset
        from peft import LoraConfig
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
        from trl import SFTTrainer
    except ImportError as exc:
        raise SystemExit("请先安装 backend/requirements-finetune.txt 中的可选依赖。") from exc

    data_path = Path(args.data)
    if not data_path.exists():
        raise SystemExit(f"训练数据不存在：{data_path}，请先运行 build_sft_dataset.py。")

    dataset = load_dataset("json", data_files=str(data_path), split="train")
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_quant_type="nf4")
    model = AutoModelForCausalLM.from_pretrained(args.model, device_map="auto", trust_remote_code=True, quantization_config=quantization)
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        task_type="CAUSAL_LM",
    )

    def formatting_func(example):
        return tokenizer.apply_chat_template(example["messages"], tokenize=False, add_generation_prompt=False)

    training_args = TrainingArguments(
        output_dir=args.output,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        logging_steps=10,
        save_strategy="epoch",
        bf16=torch.cuda.is_available(),
        report_to=[],
    )
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        peft_config=peft_config,
        formatting_func=formatting_func,
        args=training_args,
        max_seq_length=1024,
    )
    trainer.train()
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)
    print(f"Saved LoRA adapter to {args.output}")


if __name__ == "__main__":
    main()
