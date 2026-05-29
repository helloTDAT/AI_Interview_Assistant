# 微调加分项演示链路

本目录提供轻量 QLoRA/SFT 工程链路，用于展示项目具备垂类模型适配能力。MVP 默认仍使用 ChatAnywhere；本地 LoRA adapter 只作为可选增强。

## 1. 构建数据集

```powershell
cd D:\vibeCoding\project\AI_Interview_Assistant
.\backend\.venv\Scripts\python.exe backend\finetune\build_sft_dataset.py --output backend\finetune\data\interview_sft.jsonl
```

数据来源包括内置题库、本地 RAG chunks、简历优化示例和答题评分示例。输出为 ChatML 风格 JSONL。

## 2. 安装可选依赖

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-finetune.txt
```

训练建议使用具备 CUDA 的环境；本项目不要求演示机必须完成真实训练。

## 3. 训练 QLoRA Adapter

```powershell
cd D:\vibeCoding\project\AI_Interview_Assistant
.\backend\.venv\Scripts\python.exe backend\finetune\train_qlora.py --model Qwen/Qwen2.5-0.5B-Instruct --data backend\finetune\data\interview_sft.jsonl --output backend\finetune\adapters\interview-qlora
```

## 4. 切换本地微调模型

在 `.env` 中配置：

```env
ENABLE_LOCAL_FINETUNED_LLM=true
LOCAL_FINETUNED_MODEL_PATH=Qwen/Qwen2.5-0.5B-Instruct
LOCAL_LORA_ADAPTER_PATH=backend/finetune/adapters/interview-qlora
```

本地模型加载失败时，系统会自动回退到 ChatAnywhere 或规则逻辑，不影响主流程。
