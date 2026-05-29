# AGENTS.md

本文件是“智能面试助手”项目的 Agent 开发与协作指南。后续任何开发者或 AI 编程助手在修改本项目时，应优先阅读本文件，并遵守这里定义的架构边界、接口约定、测试要求和产品原则。

## 1. 项目定位

本项目是面向大学生就业场景的 Web MVP。系统以统一对话入口为核心，由 Router Agent 调度多个子 Agent，为学生提供从简历分析、模拟面试、真实面试录音复盘到个性化练习题生成的全链路辅助。

核心目标：

- 让用户通过一个对话框完成大部分操作。
- 支持通过右侧快捷入口唤起不同功能 Agent。
- 支持 PDF、DOCX、PNG、JPG、JPEG 等多格式简历输入。
- 支持用户先挂载文件，再在对话框中补充个性化需求，最后才触发分析。
- 支持岗位分类选择，并让目标岗位真实影响简历分析、模拟面试和练习题推荐。
- 支持可选 JD 粘贴；不填 JD 也能完整分析，填写 JD 时额外生成具体岗位匹配诊断。
- 支持录音复盘异步任务流、讲师批注和讲师修正。
- 支持本地 RAG 检索增强，用于练习推荐、答题反馈和复盘诊断。

## 2. 技术栈

后端：

- Python
- FastAPI
- Pydantic
- pytest
- python-docx
- pypdf
- Pillow
- pydub
- websockets
- LangGraph

前端：

- Vue 3
- Vite
- ECharts
- Vitest
- 单页聊天工作台体验，入口为 `frontend/index.html`，业务代码位于 `frontend/src`

当前 AI 与检索能力：

- ChatAnywhere OpenAI 兼容接口，默认模型 `gpt-5-mini`。
- ChatAnywhere 用于题目生成、答题评分、参考答案、模拟面试生成与总结等文本能力。
- `backend/finetune` 提供轻量 QLoRA/SFT 演示链路，用于构造垂类数据集、训练 LoRA adapter 和评估本地微调模型；默认关闭，不影响主流程。
- Planner Agent 和 ToolRegistry 用于跨任务规划、工具调用轨迹展示和安全 fallback；不得绕过附件“先挂载、后发送”的产品规则。
- 讯飞客户端封装在 `backend/app/services/xfyun_clients.py`，覆盖语音听写、Spark X1.5 HTTP 和 Embedding。
- 音频分片在 `backend/app/services/audio_processing.py`，依赖 `ffmpeg + pydub`。
- 本地 RAG 在 `backend/app/services/learning_rag.py`，前台默认走 local provider。
- 没有 API Key、调用失败、超时、限流或返回格式异常时，必须自动回退规则逻辑。
- 云端 LLM、OCR、语音识别、多模态能力应集中接入 `backend/app/services`，不要把供应商调用散落到 Agent、路由或前端。
- API Key 只能放在后端 `.env` 或系统环境变量中，严禁写入源码、测试、前端或文档示例的真实值。

## 3. 目录结构

```text
.
├── AGENTS.md
├── README.md
├── package.json
├── package-lock.json
├── vite.config.js
├── .env.example
├── backend
│   ├── app
│   │   ├── agents
│   │   │   ├── audio_agent.py
│   │   │   ├── mock_interview_agent.py
│   │   │   ├── question_agent.py
│   │   │   ├── resume_agent.py
│   │   │   └── router_agent.py
│   │   ├── api
│   │   │   └── routes.py
│   │   ├── core
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── storage.py
│   │   ├── services
│   │   │   ├── ai_clients.py
│   │   │   ├── audio_processing.py
│   │   │   ├── learning_rag.py
│   │   │   ├── resume_parser.py
│   │   │   └── xfyun_clients.py
│   │   ├── main.py
│   │   └── models.py
│   ├── requirements.txt
│   └── tests
└── frontend
    ├── index.html
    ├── smoke-test.mjs
    └── src
        ├── App.vue
        ├── main.js
        ├── styles.css
        ├── components
        ├── utils
        └── __tests__
```

## 4. 运行方式

后端启动：

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

如果 `.venv` 不存在：

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

前端首次安装依赖：

```powershell
npm install --cache .npm-cache
```

前端启动：

```powershell
npm run dev -- --host 127.0.0.1
```

前端访问地址：

```text
http://127.0.0.1:5173
```

注意：前端已迁移到 Vue + Vite，不再支持“直接双击打开 `frontend/index.html`”作为完整运行方式。

## 5. 环境变量

`.env.example` 只放变量名和安全默认值，不允许放真实 Key。`.env` 可放在项目根目录或 `backend/.env`。

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

## 6. 测试命令

后端测试：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest --basetemp .pytest-tmp
```

前端构建：

```powershell
npm run build
```

前端冒烟测试：

```powershell
node frontend\smoke-test.mjs
```

任何修改 Agent、接口、简历解析、RAG、前端交互或报告可视化的提交，都应至少通过以上三条命令。

## 7. Agent 总体架构

系统由一个 Router Agent 和四类核心子 Agent 组成：

- Router Agent
- Resume Evaluation Agent
- Mock Interview Agent
- Interview Audio Analysis Agent
- Question Generation Agent

设计原则：

- Router Agent 负责理解用户意图和调度，不直接做复杂业务分析。
- 子 Agent 只负责自己的业务域，避免互相直接依赖。
- 公共能力放到 `services`，例如 LLM、音频处理、讯飞客户端、简历解析、本地 RAG。
- 数据模型统一放在 `models.py`。
- SQLite 用于账号、权限、任务、复盘和批注；`InMemoryStore` 仍保留给部分 MVP 业务数据。

## 8. Router Agent

文件：

```text
backend/app/agents/router_agent.py
```

职责：

- 识别用户自然语言意图。
- 将用户请求分发到相应功能入口。
- 对未明确的请求返回可操作提示。
- 对学习资源类请求，可以直接调度 Question Generation Agent。

当前意图类型：

- `resume_analysis`
- `mock_interview`
- `audio_analysis`
- `learning_resource`
- `general_chat`

注意：

- Router Agent 不应直接解析简历文件。
- Router Agent 不应直接处理音频转写。
- 如果前端已经挂载了文件，前端会直接调用对应上传接口；Router 主要处理纯文本意图。

## 9. Resume Evaluation Agent

文件：

```text
backend/app/agents/resume_agent.py
backend/app/services/resume_parser.py
backend/app/services/ai_clients.py
```

职责：

- 接收已上传的简历文件路径。
- 调用 ResumeParser 完成多格式解析。
- 生成标准化 `ResumeProfile`。
- 执行规则评分、违禁词检测、模板相似度判断。
- 根据目标岗位生成岗位适配分析。
- 可选调用 ChatAnywhere `gpt-5-mini` 生成多维评价。
- 根据可选 JD 生成具体岗位匹配诊断。
- 根据用户补充需求生成更聚焦的改进建议。
- 识别真实经历块，避免把“项目背景”“项目成果”“工作内容”等标题当成项目经历。

接口：

```text
POST /files/resume
```

表单字段：

- `file`
- `user_id`
- `target_position`
- `user_instruction`
- `job_description`

重要产品原则：

- 上传文件不等于立即分析。前端应先挂载附件，等待用户补充需求后再调用 `/files/resume`。
- 用户只选择目标岗位，也必须能完成完整分析。
- 简历分析成功后应成为当前用户的共享简历画像，模拟面试和练习题在未上传新简历前必须复用这份画像。
- JD 是可选增强能力，不能变成主流程必填项。
- 当 `parse_confidence < 0.6` 或 `needs_user_confirmation = true` 时，前端必须提示用户当前结论存在不确定性。
- 不能基于 OCR 或 fallback 占位文本输出过度自信结论。
- 用户的 `target_position` 和 `user_instruction` 都必须传入分析接口。
- 如果 LLM 调用失败，必须自动回退规则分析，不能阻断简历报告生成。
- 动态预警和 STAR 胶囊只应基于具体经历句生成，不应因为孤立标题或泛词出现就判定风险。

## 10. Mock Interview Agent

文件：

```text
backend/app/agents/mock_interview_agent.py
```

接口：

```text
POST /interviews/mock/start
POST /interviews/mock/message
POST /interviews/mock/finish
```

职责：

- 根据目标岗位和已有简历报告生成完整模拟面试流程。
- 支持三种模式：`tech_blitz`、`project_deep_dive`、`behavioral`。
- 默认采用 8 题标准流程，而不是单纯项目深挖。
- 根据用户回答生成反馈、关键词、压力指标、能力分数和下一阶段。
- 点击“结束面试”时调用 `/finish` 强制中断，直接生成总结，不再继续追问。

标准 8 题流程：

1. 项目暖场
2. 项目基础题
3. 项目技术基础题
4. 项目实现细节题
5. 项目深挖题
6. 岗位/计算机基础题
7. 算法/编码思维题
8. 系统设计/行为抗压题

注意：

- 有简历时，先从真实项目或实习经历中选择最适配目标岗位的锚点。
- 无简历时，不生成任何项目经历假设，只问岗位认知、岗位基础、计算机基础、算法、系统设计、开放问题和行为抗压。
- 前端发送按钮和 Enter 键都应把输入作为面试回答提交到 `/interviews/mock/message`。
- 不要让面试中的回答误走 `/chat`。
- `finished=true` 后不得继续生成新题。

## 11. Interview Audio Analysis Agent

文件：

```text
backend/app/agents/audio_agent.py
backend/app/services/audio_processing.py
backend/app/services/xfyun_clients.py
```

接口：

```text
POST /interviews/audio
GET /tasks
GET /tasks/{task_id}
GET /reviews/{review_id}
POST /reviews/{review_id}/annotations
PUT /reviews/{review_id}/segments/{segment_id}
```

职责：

- 接收真实面试录音文件。
- 创建异步任务，返回任务 ID、进度和阶段。
- 用 `ffmpeg + pydub` 对 MP3/WAV/M4A 等格式做 16k 单声道分片准备。
- 封装讯飞语音听写 WebSocket 作为主 ASR 链路。
- 使用 Spark X1.5 HTTP 做结构化分析。
- 使用本地 RAG 做知识点诊断和漏点提示。
- 提取真实面试官问题，去重、打标签并反哺题库。
- 生成复盘控制室数据，支持讲师批注和讲师修正。

前端要求：

- 上传录音只挂载附件，不立即处理。
- 用户点击发送后才调用 `/interviews/audio`。
- 任务队列只在有录音任务时显示，不常驻占据右侧快捷入口。
- 进入复盘控制室后隐藏普通底部对话框，使用复盘工作台内部交互。
- 复盘控制室必须支持返回工作台。
- 讲师登录后必须提供退出入口；退出后清空 token、任务、复盘状态并停止轮询。

数据边界：

- 系统提示段和演示示例内容不得沉淀为真实真题。
- 示例复盘内容可用于演示，但不能写入 `real_interview` 题库或正式 RAG 诊断。
- 讲师修正应保留 AI 初评与人工修正的差异。

## 12. Question Generation Agent 与本地 RAG

文件：

```text
backend/app/agents/question_agent.py
backend/app/services/learning_rag.py
backend/scripts/import_open_source_questions.py
```

接口：

```text
POST /learning/feed
POST /learning/answers
GET /learning/mistakes/{user_id}
GET /learning/insights/{user_id}
POST /learning/questions
GET /questions
POST /questions
PUT /questions/{question_id}
DELETE /questions/{question_id}
```

职责：

- 根据简历技能、目标岗位、真实题库、本地 RAG 和上一题表现生成练习 feed。
- 为答题提交生成评分、亮点、改进点和资深工程师参考思路。
- 维护错题本和技能点亮图谱。
- 将真实面试题同步沉淀为本地 RAG chunk。

题目模型要求：

- `Question.title` 是短标题，建议 12-60 字，不得塞入完整长题干。
- `Question.prompt` 存放具体题干和作答要求，最多 1-3 条。
- `answer_reference` 存放参考思路。
- `source` 必须能区分 `real_interview`、`handbook`、`generated`、`open_source`。

RAG 规则：

- 默认使用 local provider，不阻塞前台 feed。
- 本地索引保存到 `.rag/learning_chunks.json`。
- 每个 chunk 必须保留 `text`、`title`、`repo`、`path`、`license`、`source_url`、`skill_tags`。
- 合法开源导入必须经过白名单和许可校验。
- 首次运行空库时允许使用内置种子库。
- 云 embedding 只能作为后台增强，不得成为前台推荐的硬依赖。

## 13. 前端交互规范

主要文件：

```text
frontend/src/App.vue
frontend/src/components/ResumeReportCard.vue
frontend/src/components/ResumeReportFullscreen.vue
frontend/src/components/HolographicInterviewRoom.vue
frontend/src/components/LearningPracticeBoard.vue
frontend/src/components/ReviewControlRoom.vue
frontend/src/components/TaskQueuePanel.vue
frontend/src/styles.css
```

前端目标是统一对话工作台，而不是多个孤立表单。

核心交互：

- 页面中间是主工作区。
- 普通聊天、简历分析和录音上传使用底部统一输入框。
- `activeMode === "practice"` 时，统一输入框必须切换为左侧侧滑抽屉，默认收起，只露出亮黄色呼出把手。
- 练习题模式的输入抽屉必须覆盖在题卡上方，不得推挤瀑布流布局，也不得重新占用底部固定空间。
- 输入框旁可以挂载简历或录音。
- 右上角是 Agent 快捷入口，只占据内容所需高度，不应铺满右侧下半区。
- 右下角是可选 JD 输入卡片和当前会话状态卡片，用来填补右下操作区空白。
- 岗位通过分类下拉选择，不要求用户手打。
- 简历分析完成后，助手回复应渲染可视化报告卡，而不是纯文字长气泡。
- 报告卡应提供“进入全屏报告”入口。

附件规则：

- 选择简历后，只显示已挂载状态，不得立即调用 `/files/resume`。
- 选择录音后，只显示已挂载状态，不得立即调用 `/interviews/audio`。
- 已挂载附件必须在输入框附近显示文件名和文件类型。
- 用户应能移除已挂载附件并重新选择文件。
- 点击“练习题”时，如果存在挂载简历，可以静默调用 `/files/resume` 生成推荐画像，再进入 `/learning/feed`。
- 进入练习题模式时，输入抽屉默认收起；点击呼出把手后可继续复用原输入框、岗位下拉、附件上传和发送逻辑。

岗位规则：

- 前端使用 `jobCategory` 和 `targetPosition` 两级下拉。
- 发送简历分析、模拟面试、练习题生成请求时，都必须带上当前目标岗位。
- 不能只展示岗位选择 UI，而不传给后端。

JD 规则：

- JD 粘贴是可选增强能力。
- 不填写 JD 时，报告中的 JD 拓扑区域应说明“基于目标岗位画像评估”。
- 填写 JD 时，请求必须传 `job_description`，报告应展示 JD 匹配率、命中项、缺失项和拓扑图。

复盘控制室规则：

- `activeMode === "review"` 时隐藏普通底部对话框。
- 复盘页面内部承担听录音、看转写、看诊断、讲师批注和修正。
- 系统提示段应渲染为轻提示卡，不得伪装成面试官提问。
- 不在 UI 中展示底层故障细节给演示用户。

## 14. 数据模型

文件：

```text
backend/app/models.py
```

关键模型：

- `ResumeProfile`
- `ResumeAnalysisReport`
- `ChatRequest`
- `ChatResponse`
- `MockInterviewStartRequest`
- `MockInterviewMessageRequest`
- `MockInterviewFinishRequest`
- `MockInterviewResponse`
- `Question`
- `LearningFeedRequest`
- `LearningAnswerRequest`
- `TaskRecord`
- `ReviewReport`
- `TranscriptSegment`
- `RagDiagnosis`
- `ReviewAnnotation`

修改模型时：

- 同步更新接口测试。
- 确认前端字段读取没有失效。
- 尽量保持向后兼容。

## 15. 存储策略

文件：

```text
backend/app/core/storage.py
backend/app/core/database.py
```

当前存储：

- SQLite：用户、token、任务、复盘、批注。
- InMemoryStore：简历报告、模拟面试 session、题库、部分能力报告和 RAG runtime cache。
- `.rag/learning_chunks.json`：本地 RAG 持久化索引。

约束：

- 不要在 Agent 内直接写复杂数据库细节。
- 数据库访问应集中在 `core/database.py` 或后续 repository 层。
- 真实密钥、本地数据库和上传文件不应提交到仓库。

## 16. 云服务接入约定

文件：

```text
backend/app/services/ai_clients.py
backend/app/services/xfyun_clients.py
```

当前接口：

- `LLMClient`
- `OCRClient`
- `SpeechClient`
- `XfyunSpeechClient`
- `XfyunSparkClient`
- `XfyunEmbeddingClient`

当前 LLM：

- Provider：ChatAnywhere
- Base URL：`https://api.chatanywhere.tech/v1`
- Model：`gpt-5-mini`
- API：OpenAI-compatible `/v1/chat/completions`

禁止：

- 在 `routes.py` 里直接调用云模型。
- 在前端暴露云服务 API Key。
- 在 Agent 内到处散落供应商 SDK 调用。
- 在测试中依赖真实外部 LLM、ASR 或 Embedding 请求。
- 把 `.env` 里的真实 Key 写入 README、AGENTS、测试快照或提交历史。

## 17. 测试规范

当前测试覆盖重点：

- Router Agent 意图识别。
- DOCX/PDF/图片简历解析和 fallback。
- 简历分析接口、岗位画像、JD 可选诊断。
- LLMClient 成功、无 Key、非 JSON、失败 fallback。
- 模拟面试 8 题流程、追问、强制结束 `/finish`。
- 录音分析任务、复盘控制室、讲师批注和讲师修正。
- 本地 RAG seed、导入、搜索、feed 和真实题沉淀。
- 前端附件挂载后不立即分析。
- 前端传递 `target_position`、`user_instruction`、可选 `job_description`。
- 前端练习题短标题、RAG 状态、加载/失败/空态。
- 前端练习题模式下 Chat Input 左侧抽屉默认收起、可展开，且不遮挡或推挤瀑布流题卡。
- 前端讲师登录、退出、任务轮询停止。

新增功能必须补测试：

- 新增 Agent：补 Agent 单元测试和 API 测试。
- 新增接口：补 FastAPI TestClient 测试。
- 修改前端主流程：补 `frontend/src/__tests__/app.spec.js` 或 `frontend/smoke-test.mjs`。
- 修改岗位画像：补至少一个岗位匹配测试。
- 修改简历解析：补对应格式或 fallback 测试。
- 修改题目模型：补短标题、prompt 和前端展示测试。

## 18. 编码与文案

所有源码文件应使用 UTF-8。

注意：

- 不要引入乱码中文。
- 中文文案要面向学生用户，避免过度技术化。
- 对不确定结果要明确表达不确定性。
- 不要把完整 JSON 作为最终主反馈展示给用户。
- LLM 输出中涉及量化成果时，不能伪造简历中不存在的数据；应使用“建议补充/可改写为”的语气。
- 面试题要可读，避免把长段要求全部塞进标题。
- 复盘演示文案应自然，但内部不能把示例数据当真实结果沉淀。

推荐语气：

- 清楚、具体、可执行。
- 给出下一步建议。
- 对低置信度解析明确提示原因和补救方式。

## 19. 当前已知限制

MVP 阶段仍有以下限制：

- OCR 和 ASR 已有封装与 fallback，但真实连通性需要本地填写密钥后手动验证。
- 本地 RAG 是轻量检索增强，不是生产级向量数据库。
- 部分业务数据仍是内存存储，服务重启后会丢失。
- ECharts 图表当前在 Vitest 中使用 mock，真实视觉仍需浏览器手动或 E2E 验证。
- 语音作答按钮仍是 UI 占位，不应宣称已完成真实语音识别。

这些限制不能在产品说明或演示中伪装成已完成生产级能力。

## 20. 推荐开发顺序

后续迭代建议：

1. 修复现有源码中可能残留的乱码文案。
2. 接入并验证真实 OCR。
3. 接入并验证真实讯飞 ASR 长音频链路。
4. 将 MVP 内存题库和简历报告迁移到数据库。
5. 引入可选生产级向量库或重排序能力。
6. 加入 Playwright 端到端测试和移动端布局测试。
7. 加入正式讲师后台和题库管理后台。

## 21. 修改前检查清单

开发者或 AI Agent 修改本项目时，应先确认：

- 是否会破坏统一对话入口体验？
- 是否会导致上传文件后立即执行分析？
- 是否正确传递 `target_position`？
- 是否正确传递 `user_instruction`？
- 如果填写 JD，是否正确传递 `job_description`？
- 低置信度解析是否被明确提示？
- 简历报告是否仍以可视化卡片呈现，而不是退回长文本气泡？
- 模拟面试是否仍遵循 8 题递进流程？
- 结束面试是否走 `/interviews/mock/finish`？
- 练习题 `title` 是否保持短标题？
- 练习题模式下输入框是否仍是左侧抽屉而不是底部遮挡层？
- RAG 是否保持本地快速 fallback，不阻塞前台？
- 示例复盘是否没有沉淀为真实真题？
- 讲师退出后是否清理 token、任务和轮询器？
- 是否新增或更新了测试？
- 是否通过后端测试、前端构建和前端冒烟测试？
- 是否避免把云服务 API Key 写入代码？

## 22. 完成标准

一次功能修改完成前，至少应满足：

- 后端测试通过。
- 前端构建通过。
- 前端冒烟测试通过。
- 用户主流程可以解释清楚。
- 文案没有乱码。
- 新增能力没有越权影响其他 Agent。
- README 或 AGENTS.md 在必要时同步更新。
