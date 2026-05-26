# AGENTS.md

本文件是“智能面试助手”项目的 Agent 开发与协作指南。后续任何开发者或 AI 编程助手在修改本项目时，应优先阅读本文件，并遵守这里定义的架构边界、接口约定、测试要求和产品原则。

## 1. 项目定位

本项目是一个面向大学生就业场景的 Web 应用 MVP。系统以统一对话入口为核心，通过 Router Agent 调度多个子 Agent，为学生提供从简历分析、模拟面试、真实面试录音复盘到个性化练习题生成的全链路辅助。

核心目标：

- 让用户通过一个对话框完成大部分操作。
- 支持通过旁侧快捷按钮唤起不同功能 Agent。
- 支持 PDF、DOCX、PNG、JPG、JPEG 等多格式简历输入。
- 支持用户先挂载文件，再在对话框中补充个性化需求，最后才触发分析。
- 支持岗位分类选择，并让目标岗位真实影响简历分析、模拟面试和练习题推荐。
- 支持可选 JD 粘贴：不填 JD 也能完整分析；填写 JD 时额外生成具体岗位匹配诊断。
- 当 OCR 或文本解析置信度较低时，必须明确提示“当前只是预分析”，不能假装已经完整读懂简历。

## 2. 技术栈

后端：

- Python
- FastAPI
- Pydantic
- pytest
- python-docx
- pypdf
- httpx

前端：

- Vue 3
- Vite
- ECharts
- Vitest
- 单页聊天工作台体验，入口为 `frontend/index.html`，业务代码位于 `frontend/src`

当前 AI 能力：

- 简历分析模块支持通过 ChatAnywhere 的 OpenAI 兼容接口调用 `gpt-4o-mini`。
- 没有 API Key、调用失败、超时、限流或返回格式异常时，必须自动回退到规则分析。
- OCR、语音识别仍是占位 fallback。
- 云端 LLM、OCR、语音识别、多模态能力应集中接入 `backend/app/services/ai_clients.py`，不要把供应商调用散落到各个 Agent、路由或前端内。
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
│   │   │   └── storage.py
│   │   ├── services
│   │   │   ├── ai_clients.py
│   │   │   └── resume_parser.py
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

`.env.example` 只放变量名和安全默认值，不允许放真实 Key。

ChatAnywhere 配置：

```env
LLM_PROVIDER=chatanywhere
CHATANYWHERE_API_KEY=
CHATANYWHERE_BASE_URL=https://api.chatanywhere.tech/v1
CHATANYWHERE_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=20
LLM_MAX_TOKENS=1800
```

`.env` 可放在项目根目录或 `backend/.env`。`backend/app/core/config.py` 会同时读取这两个位置。

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

或直接运行：

```powershell
npm run smoke:frontend
```

任何修改 Agent、接口、简历解析、前端交互或报告可视化的 PR 或提交，都应至少通过：

- `.\.venv\Scripts\python.exe -m pytest --basetemp .pytest-tmp`
- `npm run build`
- `node frontend\smoke-test.mjs`

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
- 公共能力放到 `services`，例如 LLM、OCR、语音识别、简历解析。
- 数据模型统一放在 `models.py`。
- MVP 阶段使用 `InMemoryStore`，后续替换数据库时应保持接口行为不变。

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
- 可选调用 ChatAnywhere `gpt-4o-mini` 生成多维评价。
- 根据可选 JD 生成具体岗位匹配诊断。
- 根据用户补充需求生成更聚焦的改进建议。

支持格式：

- `.pdf`
- `.docx`
- `.png`
- `.jpg`
- `.jpeg`

解析策略：

- PDF：优先文本层抽取；如果文本过少，则进入 OCR fallback。
- DOCX：直接抽取段落和表格内容。
- 图片：进入 OCR/multimodal fallback。
- 不支持格式：返回低置信度和警告。

接口：

```text
POST /files/resume
```

表单字段：

- `file`
- `user_id`
- `target_position`
- `user_instruction`
- `job_description`：可选，用户粘贴具体岗位 JD 时传入

报告关键字段：

- `quality_score`
- `dimension_scores`
- `forbidden_words`
- `template_similarity_score`
- `job_fit`
- `recommendations`
- `analysis_engine`：`llm`、`rules` 或 `rules_fallback`
- `llm_error`
- `jd_diagnosis`
- `interview_risks`
- `logic_gaps`
- `reading_experience`
- `star_optimizations`
- `needs_user_confirmation`

重要产品原则：

- 上传文件不等于立即分析。前端应先挂载附件，等待用户补充需求后再调用 `/files/resume`。
- 用户只选择目标岗位，也必须能完成完整分析。
- JD 是可选增强能力，不能变成主流程必填项。
- 当 `parse_confidence < 0.6` 或 `needs_user_confirmation = true` 时，前端必须提示用户当前是预分析。
- 不能基于 `[OCR待接入]` 这类占位文本输出过度自信结论。
- 用户的 `target_position` 和 `user_instruction` 都必须传入分析接口。
- 如果 LLM 调用失败，必须自动回退规则分析，不能阻断简历报告生成。

岗位匹配：

- 岗位画像定义在 `ResumeEvaluationAgent.target_skill_map`。
- 新增岗位时，应补充对应核心技能，并添加测试。
- AI/算法岗应重点关注 Python、机器学习、深度学习、PyTorch、TensorFlow、算法、SQL 等能力。

## 10. Mock Interview Agent

文件：

```text
backend/app/agents/mock_interview_agent.py
```

职责：

- 根据用户目标岗位和已有简历报告生成模拟面试问题。
- 支持多轮问答。
- 根据用户回答生成简短反馈。
- 在会话结束时生成总结反馈。

接口：

```text
POST /interviews/mock/start
POST /interviews/mock/message
```

注意：

- 如果用户已经上传过简历，应优先使用简历中的技能点生成问题。
- 模拟面试开始后，前端发送按钮和 Enter 键都应把输入作为面试回答提交到 `/interviews/mock/message`。
- 不要让面试中的回答误走 `/chat`。

## 11. Interview Audio Analysis Agent

文件：

```text
backend/app/agents/audio_agent.py
```

职责：

- 接收真实面试录音文件。
- 调用 SpeechClient 完成语音转写。
- 提取面试官问题。
- 将真实面试题沉淀到题库。
- 生成能力报告和成长建议。

接口：

```text
POST /interviews/audio
GET /tasks/{task_id}
GET /reports/{user_id}
```

当前实现：

- SpeechClient 仍是占位 fallback。
- 任务使用 FastAPI BackgroundTasks 和内存任务表。

后续接入真实语音服务时，应在 `SpeechClient.transcribe()` 中实现，不要改 Agent 主流程。

## 12. Question Generation Agent

文件：

```text
backend/app/agents/question_agent.py
```

职责：

- 根据简历技能、目标岗位、真实题库和宝典题生成练习题。
- 将系统生成题写入题库。
- 为模拟面试提供候选问题。

接口：

```text
POST /learning/questions
GET /questions
POST /questions
PUT /questions/{question_id}
DELETE /questions/{question_id}
```

注意：

- 当前是内存题库。
- 后续接入 RAG 时，应让题目生成先检索题库和面试宝典，再生成题目。
- 题目应保留来源：`real_interview`、`handbook`、`generated`。

## 13. 前端交互规范

主要文件：

```text
frontend/src/App.vue
frontend/src/components/ResumeReportCard.vue
frontend/src/components/ResumeReportFullscreen.vue
frontend/src/components/AbilityRadar.vue
frontend/src/components/JdTopology.vue
frontend/src/components/ScoreRing.vue
frontend/src/components/ComplianceBadges.vue
frontend/src/components/RiskInsightPanel.vue
frontend/src/components/StarDiffCapsules.vue
frontend/src/utils/normalizeResumeReport.js
frontend/src/styles.css
```

前端目标是统一对话工作台，而不是多个孤立表单。

核心交互：

- 页面中间是聊天流。
- 底部是统一输入框。
- 输入框旁可以挂载简历或录音。
- 右上角是 Agent 快捷入口，只占据内容所需高度，不应铺满整个右侧下半区。
- 右下角是可选 JD 输入卡片和当前会话状态卡片，用来填补右下操作区空白。
- 岗位通过分类下拉选择，不要求用户手打。
- 简历分析完成后，助手回复应渲染可视化报告卡，而不是纯文字长气泡。
- 报告卡应提供“进入全屏报告”入口。

当前布局约定：

- 页面整体保持左侧窄导航、中间主工作区、右侧辅助区的稳定结构。
- `Agent 快捷入口` 位于右侧辅助区上方，视觉上是独立卡片组，不要占满右侧整列高度。
- `JD 卡片` 和 `当前会话` 位于右下角，宽度应比普通窄卡片更舒展，避免文字过早换行。
- 底部对话框应在可用主区域内居中，不要贴左；同时要给右下角 JD/会话卡片保留空间。
- 修改 `frontend/src/styles.css` 时要特别关注 `.composer-console`、`.input-context`、`.side`、`.messages`、`.hero` 的相互影响。
- 顶部状态胶囊 `Router Agent 待命` 应位于主顶部栏右侧，不放入 Agent 快捷入口标题行。

附件规则：

- 选择简历后，只显示已挂载状态，不得立即调用 `/files/resume`。
- 已挂载附件必须在输入框附近显示文件名和文件类型，例如 `resume.docx / DOCX 简历`，方便用户确认选中的文件是否正确。
- 用户点击发送后，如果存在挂载简历，则调用 `/files/resume`，并传入输入框内容作为 `user_instruction`。
- 选择录音后，只显示已挂载状态，不得立即调用 `/interviews/audio`。
- 用户应能移除已挂载附件并重新选择文件。
- 用户点击发送后，如果存在挂载录音，则调用 `/interviews/audio`。

岗位规则：

- 前端使用 `jobCategory` 和 `targetPosition` 两级下拉。
- 发送简历分析、模拟面试、练习题生成请求时，都必须带上当前目标岗位。
- 不能只展示岗位选择 UI，而不传给后端。

JD 规则：

- JD 粘贴是可选增强能力。
- 不填写 JD 时，报告中的 JD 拓扑区域应说明“基于目标岗位画像评估”。
- 填写 JD 时，请求必须传 `job_description`，报告应展示 JD 匹配率、命中项、缺失项和拓扑图。

简历可视化报告要求：

- 顶部 Overview：综合得分环、模板查重状态、违禁词状态、解析置信度状态。
- 中部 Visual Charts：ECharts 能力雷达图、ECharts JD 匹配拓扑图。
- 右侧 Alert & Insights：面试雷区、AI 预测追问、逻辑断层、阅读体验短卡片。
- 底部 STAR 修改胶囊：Before / After / 优化动作说明三列 diff 风格展示。
- 不应把完整 JSON 直接甩给普通用户作为主反馈。
- 低置信度时必须显示“预分析”提示，避免过度确定表达。

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
- `MockInterviewResponse`
- `Question`
- `TaskRecord`
- `AbilityReport`

修改模型时：

- 同步更新接口测试。
- 确认前端 `normalizeResumeReport()` 字段读取没有失效。
- 尽量保持向后兼容。

## 15. 存储策略

文件：

```text
backend/app/core/storage.py
```

当前使用 `InMemoryStore`，包括：

- `resume_reports`
- `mock_sessions`
- `tasks`
- `questions`
- `reports`

后续替换数据库时，建议：

- 使用 PostgreSQL 作为主库。
- 使用 pgvector 或 Qdrant 作为向量检索。
- 把题库、面试宝典、岗位 JD、真实面试题都纳入 RAG。

不要在 Agent 内直接写数据库细节。应抽象存储层或 repository 层。

## 16. 云服务接入约定

文件：

```text
backend/app/services/ai_clients.py
```

所有云 API 接入必须集中在这里或同级 service 文件中。

当前接口：

- `LLMClient`
- `OCRClient`
- `SpeechClient`

当前 LLM：

- Provider：ChatAnywhere
- Base URL：`https://api.chatanywhere.tech/v1`
- Model：`gpt-4o-mini`
- API：OpenAI-compatible Chat Completions `/chat/completions`

禁止：

- 在 `routes.py` 里直接调用云模型。
- 在前端暴露云服务 API Key。
- 在 Agent 内到处散落供应商 SDK 调用。
- 在测试中依赖真实外部 LLM 请求；测试应 mock LLMClient 或传空 Key。

云能力替换方向：

- OCR：图片简历、扫描 PDF。
- LLM：结构化简历抽取、综合分析、模拟面试追问、练习题生成。
- Speech：真实面试录音转写、说话人分离。
- RAG：面试宝典、真实题库、岗位 JD、公开答案资料。

## 17. 测试规范

当前测试覆盖：

- Router Agent 意图识别。
- DOCX 简历解析。
- 图片简历 OCR fallback。
- 简历分析接口。
- AI 算法岗岗位匹配。
- LLMClient JSON 调用、无 Key、非 JSON fallback。
- LLM 简历分析成功与失败规则兜底。
- 模拟面试流程。
- 录音分析任务创建。
- 前端附件挂载后不立即分析。
- 前端发送需求后再调用简历分析接口。
- 前端传递 `target_position`、`user_instruction`、可选 `job_description`。
- 前端显示已挂载文件的文件名和文件类型。
- 前端保持右上 Agent 快捷入口、右下 JD/会话卡片、底部输入框居中的布局约定。
- 前端渲染简历报告卡、得分环、合规 Badge、雷达图容器、JD 拓扑容器、面试雷区、STAR diff。
- 前端全屏报告打开与关闭。
- 前端模拟面试中发送按钮走面试回答接口。

新增功能必须补测试：

- 新增 Agent：补 Agent 单元测试和 API 测试。
- 新增接口：补 FastAPI TestClient 测试。
- 修改前端主流程：补 `frontend/src/__tests__/app.spec.js` 和 `frontend/smoke-test.mjs`。
- 修改岗位画像：补至少一个岗位匹配测试。
- 修改简历解析：补对应格式或 fallback 测试。
- 修改简历报告字段：补 `normalizeResumeReport()` 或组件渲染测试。

## 18. 编码与文案

所有源码文件应使用 UTF-8。

注意：

- 不要引入乱码中文。
- 中文文案要面向学生用户，避免过度技术化。
- 对不确定结果要明确表达不确定性。
- 不要把调试 JSON 作为最终主回答展示给用户。
- LLM 输出中涉及量化成果时，不能伪造简历中不存在的数据；应使用“建议补充/可改写为”的语气。

推荐语气：

- 清楚、具体、可执行。
- 给出下一步建议。
- 对低置信度解析明确提示原因和补救方式。

## 19. 当前已知限制

MVP 阶段仍有以下限制：

- OCR 未接入真实云服务。
- Speech-to-text 未接入真实云服务。
- RAG 知识库尚未实现。
- 数据存储仍是内存，服务重启后数据会丢失。
- 尚未进行真实浏览器 Playwright 视觉回归测试。
- ECharts 图表当前在 Vitest 中使用 mock，真实视觉仍需浏览器手动或 E2E 验证。

这些限制不能在用户界面中伪装成已完成能力。需要明确以“待接入”“预分析”“当前解析置信度较低”等方式提示用户。

## 20. 推荐开发顺序

后续迭代建议按以下顺序推进：

1. 接入真实 OCR，解决图片简历和扫描 PDF 解析问题。
2. 强化 LLM 结构化输出校验，提升简历多维报告稳定性。
3. 引入数据库，替换 InMemoryStore。
4. 建立题库和面试宝典 RAG。
5. 接入真实语音识别和说话人分离。
6. 加入 Playwright 端到端测试和移动端布局测试。
7. 加入讲师审核后台和题库管理后台。

## 21. 修改前检查清单

开发者或 AI Agent 修改本项目时，应先确认：

- 是否会破坏统一对话入口体验？
- 是否会导致上传文件后立即执行分析？
- 是否正确传递 `target_position`？
- 是否正确传递 `user_instruction`？
- 如果填写 JD，是否正确传递 `job_description`？
- 低置信度 OCR 是否被明确提示？
- 简历报告是否仍以可视化卡片呈现，而不是退回长文本气泡？
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
