# 智能面试助手

面向大学生就业场景的 LangChain/LangGraph 风格多 Agent Web 应用 MVP。系统以统一对话入口调度简历分析、模拟面试、真实面试录音复盘、个性化练习题生成四个核心模块。

## 当前实现

- FastAPI 后端接口骨架
- Router Agent 意图识别与任务调度
- Resume Evaluation Agent
  - 支持 `.pdf`、`.docx`、`.png/.jpg/.jpeg` 简历入口
  - PDF 文本层优先，文本不足时标记 OCR fallback
  - 图片简历走 OCR/多模态适配器
  - 输出统一 `ResumeProfile`
- Mock Interview Agent 多轮模拟面试
- Interview Audio Analysis Agent 真实录音分析任务骨架
- Question Generation Agent 个性化练习题生成
- 内存版题库、任务、报告存储
- 轻量前端页面
- pytest 基础测试

## 前端交互说明

- 上传简历或录音后不会立刻执行分析，只会先挂载到对话框。
- 用户可以在对话框补充需求，例如“我想面试 AI 算法岗，请重点优化项目经历”，点击发送后才会调度对应 Agent。
- 岗位选择采用分类下拉：技术研发、AI/算法、数据岗位、产品运营、测试质量。
- 简历分析会同时使用岗位选择和用户补充需求生成结果。
- 如果 PDF 是扫描版或图片 OCR 置信度低，系统会明确提示“当前只是预分析”，不会假装已经完整读懂简历。

## 目录

```text
backend/
  app/
    agents/
    api/
    core/
    services/
    main.py
  tests/
frontend/
  index.html
```

## 运行后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

打开 `http://127.0.0.1:8000/docs` 查看接口文档。

## 运行测试

```bash
cd backend
pytest
```

前端脚本冒烟测试：

```bash
cd ..
C:\Users\IkeTDAT\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe frontend\smoke-test.mjs
```

## 云服务接入点

当前 `backend/app/services/ai_clients.py` 提供可替换适配器：

- `LLMClient`
- `OCRClient`
- `SpeechClient`

后续可将其中的规则 fallback 替换为 OpenAI、通义、讯飞、火山等云 API。
## 前端运行方式

前端已迁移为 Vue + Vite + ECharts 应用。首次运行先安装依赖：

```powershell
npm install --cache .npm-cache
```

启动前端：

```powershell
npm run dev -- --host 127.0.0.1
```

访问：

```text
http://127.0.0.1:5173
```

构建和前端冒烟测试：

```powershell
npm run build
node frontend\smoke-test.mjs
```

## ChatAnywhere gpt-4o-mini 配置

简历分析模块支持通过 ChatAnywhere 的 OpenAI 兼容接口调用 `gpt-4o-mini`。密钥只允许放在后端环境变量或 `.env` 中，不能写入源码、测试或前端。

1. 复制 `.env.example` 为 `.env`。
2. 填写 `CHATANYWHERE_API_KEY`。
3. 启动后端后，上传简历时如果 key 可用会优先使用 LLM 生成多维评价；如果未配置、超时、限流或返回格式异常，会自动回退到规则分析。

```env
LLM_PROVIDER=chatanywhere
CHATANYWHERE_API_KEY=your-new-key
CHATANYWHERE_BASE_URL=https://api.chatanywhere.tech/v1
CHATANYWHERE_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=20
LLM_MAX_TOKENS=1800
```
