# 智能面试助手

智能面试助手是一个面向大学生求职场景的 Web MVP。系统以统一对话入口为核心，由 Router Agent 调度简历评估、沉浸式模拟面试、录音复盘控制室和学习练习瀑布流，帮助用户完成从简历诊断到面试训练、复盘和个性化刷题的闭环。

## 核心能力

- **简历评估**：支持 PDF、DOCX、PNG、JPG、JPEG 等简历输入，结合目标岗位和可选 JD 生成可视化体检报告、能力雷达、风险提示、STAR 改写建议和岗位匹配诊断。
- **沉浸式模拟面试**：基于目标岗位和已解析简历生成 8 题递进式技术面流程，覆盖项目暖场、项目基础、实现细节、项目深挖、岗位基础、算法、系统设计和行为抗压；支持强制结束并即时生成总结。
- **录音复盘控制室**：录音上传后进入异步任务流，完成后进入复盘工作台，展示逐句剧本、时间轴、RAG 诊断、讲师批注和讲师修正入口。
- **学习练习瀑布流**：练习卡采用短标题 + 题干说明，支持基于简历技能、目标岗位、真实面试题、本地 RAG 和上一题表现动态推荐。
- **共享简历画像**：一次简历分析成功后，模拟面试和练习题会复用最近一次简历画像；上传新简历会覆盖旧画像。
- **本地 RAG**：默认使用轻量本地检索，不阻塞前台推荐；支持合法开源 Markdown 导入、内置种子库和真实面试题沉淀。
- **讲师复核**：SQLite 持久化账号、任务、复盘和批注；讲师可登录、查看任务、批注、修正转写和退出登录。

## 技术栈

后端：

- Python
- FastAPI
- Pydantic
- pytest
- python-docx / pypdf / Pillow
- pydub / ffmpeg
- websockets
- LangGraph

前端：

- Vue 3
- Vite
- ECharts
- Vitest

AI 与检索：

- ChatAnywhere OpenAI 兼容接口，默认模型 `gpt-5-mini`
- 讯飞语音听写、Spark X1.5 HTTP、讯飞 Embedding 的客户端封装
- 本地 BM25/TF-IDF 风格 RAG + 本地 embedding fallback
- 可选 QLoRA/SFT 微调演示链路，默认关闭，不影响云端模型主流程
- Planner Agent + ToolRegistry，用于跨任务规划、工具调用轨迹展示和安全 fallback

## Planner Agent 与微调加分项

- **Planner Agent**：Router 识别到“规划、训练路径、先做 A 再做 B”等跨任务请求时，会调用 Planner Agent。Planner 通过工具注册表复用简历画像、RAG 检索、练习题推荐和模拟面试启动能力，并返回执行轨迹。
- **微调链路**：`backend/finetune` 提供 SFT 数据集构建、QLoRA 训练脚本、adapter 评估脚本和演示文档。默认仍使用 ChatAnywhere；设置 `ENABLE_LOCAL_FINETUNED_LLM=true` 后可尝试加载本地模型和 LoRA adapter。
- **演示口径**：当前项目具备基于简历、面试题、RAG 知识片段构造垂类 SFT 数据并适配开源模型的工程链路；不宣称已经完成生产级大规模训练。

## 目录结构

```text
.
├── backend
│   ├── app
│   │   ├── agents
│   │   ├── api
│   │   ├── core
│   │   ├── services
│   │   ├── main.py
│   │   └── models.py
│   ├── requirements.txt
│   └── tests
├── frontend
│   ├── index.html
│   ├── smoke-test.mjs
│   └── src
├── .env.example
├── AGENTS.md
├── README.md
├── package.json
└── vite.config.js
```

## 快速启动

### 1. 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

### 2. 前端

```powershell
npm install --cache .npm-cache
npm run dev -- --host 127.0.0.1
```

访问地址：

```text
http://127.0.0.1:5173
```

注意：前端是 Vue + Vite 应用，不能直接双击 `frontend/index.html` 作为完整运行方式。

### 3. 完整验证

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest --basetemp .pytest-tmp
```

```powershell
npm run build
node frontend\smoke-test.mjs
```

## 环境变量

复制 `.env.example` 为 `.env`，可放在项目根目录或 `backend/.env`。真实 Key 只允许放在本地 `.env` 或系统环境变量中，严禁提交到 GitHub。

```env
LLM_PROVIDER=chatanywhere
CHATANYWHERE_API_KEY=
CHATANYWHERE_BASE_URL=https://api.chatanywhere.tech/v1
CHATANYWHERE_MODEL=gpt-5-mini
CHATANYWHERE_EMBEDDING_MODEL=text-embedding-ada-002
LLM_TIMEOUT_SECONDS=20
LLM_MAX_TOKENS=1800
RAG_VECTOR_DIR=.rag

DATABASE_PATH=interview_assistant.sqlite3

XFYUN_APP_ID=
XFYUN_API_KEY=
XFYUN_API_SECRET=
XFYUN_SPARK_API_PASSWORD=
XFYUN_SPARK_BASE_URL=https://spark-api-open.xf-yun.com/v2
XFYUN_SPARK_MODEL=spark-x
XFYUN_EMBEDDING_URL=https://emb-cn-huabei-1.xf-yun.com/
XFYUN_IAT_URL=wss://iat-api.xfyun.cn/v2/iat
AUDIO_CHUNK_SECONDS=55
```

音频分片依赖 `ffmpeg + pydub`。如果需要处理 MP3、M4A 等多格式长音频，请确保运行环境已安装并能在命令行访问 `ffmpeg`。

## 核心模块

### Resume Evaluation Agent

入口：`POST /files/resume`

能力：

- 多格式简历解析。
- 目标岗位画像匹配。
- 可选 JD 匹配诊断。
- 综合评分、能力雷达、风险提醒、STAR 改写和阅读体验建议。
- LLM 调用失败时自动回退规则分析。

交互边界：

- 上传简历只是挂载附件，不会立即分析。
- 点击发送后，前端才会携带 `target_position`、`user_instruction` 和可选 `job_description` 调用后端。
- 低置信度解析必须提示不确定性，不能伪造已完整读懂。

### Mock Interview Agent

入口：

- `POST /interviews/mock/start`
- `POST /interviews/mock/message`
- `POST /interviews/mock/finish`

标准流程：

1. 项目暖场
2. 项目基础
3. 项目技术基础
4. 项目实现细节
5. 项目深挖
6. 岗位/计算机基础
7. 算法/编码思维
8. 系统设计/行为抗压

有简历时，系统会从真实项目或实习经历中选择岗位相关锚点；无简历时，不生成虚构项目，只问岗位基础、计算机基础、算法、系统设计和开放问题。点击“结束面试”会直接调用 `/interviews/mock/finish`，立即中断并生成与完整结束一致结构的总结报告。

### Audio Analysis Agent

入口：

- `POST /interviews/audio`
- `GET /tasks`
- `GET /tasks/{task_id}`
- `GET /reviews/{review_id}`
- `POST /reviews/{review_id}/annotations`
- `PUT /reviews/{review_id}/segments/{segment_id}`

能力：

- 录音上传后创建异步任务。
- 使用 `ffmpeg + pydub` 做多格式音频分片准备。
- 封装讯飞语音听写、Spark 分析和 Embedding 客户端。
- 复盘控制室展示时间轴、逐句剧本、RAG 诊断、讲师批注和讲师修正。
- 真实面试官问题经去重和标签化后可反哺题库。

说明：演示降级内容不会沉淀为真实真题，也不会作为正式 RAG 诊断来源。

### Question Generation Agent

入口：

- `POST /learning/feed`
- `POST /learning/answers`
- `GET /learning/mistakes/{user_id}`
- `GET /learning/insights/{user_id}`
- `GET /questions`

能力：

- 题卡标题保持短标题，完整作答要求放在 `prompt`。
- 用户挂载简历后，不必点击发送；点击“练习题”会先静默生成推荐画像，再进入个性化练习流。
- Feed 综合简历技能、目标岗位、真实面试题、本地 RAG 命中和上一题表现排序。
- 进入练习瀑布流后，主对话框会切换为左侧抽屉，默认收起，只保留亮黄色呼出把手，避免遮挡底部题卡。
- 支持错题本和技能点亮图谱。

## 本地 RAG 与数据来源

本项目默认使用轻量本地 RAG，核心文件为：

```text
.rag/learning_chunks.json
backend/app/services/learning_rag.py
backend/scripts/import_open_source_questions.py
```

设计原则：

- 前台推荐和复盘诊断默认走本地检索，不等待云 embedding，避免卡在“正在推荐”。
- 首次运行时可使用内置种子库，覆盖 Redis、MySQL、Java 并发、Spring、算法、Agent/RAG 等常见题。
- 合法开源资料导入必须经过白名单和许可校验，并保留 `license`、`repo`、`path`、`source_url`。
- 支持将真实面试题写入题库并同步为本地 RAG chunk。
- 云 embedding 是可选增强，不是前台同步链路的硬依赖。

## 演示流程

1. 选择岗位方向和目标岗位。
2. 上传简历，输入需求后点击发送，生成简历体检报告。
3. 点击“模拟面试”，进入全息面试舱，体验 8 题递进面试。
4. 点击“结束面试”，立即中断并生成本轮面试评估。
5. 上传录音，任务队列显示处理进度；完成后进入复盘控制室。
6. 讲师登录后查看复盘、添加批注、修正角色/文本/分数，再退出登录。
7. 点击“练习题”，进入基于简历画像、岗位、RAG 和表现信号推荐的瀑布流练习场；如需继续向助手发送消息，可从左侧亮黄色把手呼出对话抽屉。

## 数据与安全

- API Key 不得写入源码、前端、测试、README、AGENTS 或提交历史。
- `.env` 和本地数据库文件不应提交。
- 前端永远不接触 ChatAnywhere 或讯飞密钥。
- 测试应 mock 外部模型调用，不能依赖真实云服务。
- 示例复盘内容只用于演示，不得作为真实真题沉淀。

## 当前边界

- OCR 和 ASR 具备服务封装与 fallback，但真实连通性需要填写本地密钥后手动验证。
- 本地 RAG 是轻量版检索增强，不引入 FAISS、PyTorch 或 sentence-transformers 等重依赖。
- SQLite 用于账号、权限、任务、复盘和批注；部分 MVP 业务数据仍保留在内存存储中。
- ECharts 在测试环境中使用 mock，最终视觉效果仍建议浏览器人工复核。
