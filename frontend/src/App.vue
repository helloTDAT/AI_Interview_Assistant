<template>
  <div class="app-shell">
    <nav class="rail" aria-label="主导航">
      <div class="mark">AI</div>
      <button type="button" class="rail-button" title="新会话" @click="newThread">+</button>
      <button type="button" class="rail-button" title="简历分析" @click="quickPrompt('请帮我分析简历，我会上传 PDF、DOCX 或图片简历。')">CV</button>
      <button type="button" class="rail-button" title="模拟面试" @click="startMock">MI</button>
      <button type="button" class="rail-button" title="练习题" @click="generateQuestions">Q</button>
    </nav>

    <main class="workspace">
      <header class="topbar">
        <div>
          <h1>智能面试助手</h1>
          <p>统一对话入口自动调度简历评估、模拟面试、录音复盘和练习题 Agent。</p>
        </div>
        <div class="status-pill"><span class="dot"></span>{{ agentStatus }}</div>
      </header>

      <section ref="messagesRef" class="messages">
        <section v-if="messages.length === 0" class="hero">
          <h2>今天想先提升哪一块面试能力？</h2>
          <p>上传简历后，系统会生成可视化体检报告：得分环、雷达图、JD 拓扑、面试雷区和 STAR 修改胶囊。</p>
          <div class="suggestions">
            <button type="button" @click="quickPrompt('请帮我分析简历，目标岗位是后端开发工程师。')">
              <strong>分析简历</strong>
              <span>上传文件后再发送需求，不会立即分析。</span>
            </button>
            <button type="button" @click="startMock">
              <strong>开始模拟面试</strong>
              <span>根据目标岗位多轮追问并给出反馈。</span>
            </button>
            <button type="button" @click="generateQuestions">
              <strong>生成练习题</strong>
              <span>结合简历技能点生成训练题。</span>
            </button>
          </div>
        </section>

        <div class="thread" data-testid="thread">
          <article
            v-for="messageItem in messages"
            :key="messageItem.id"
            class="message"
            :class="[messageItem.role, messageItem.type === 'resume-report' ? 'report-message' : '']"
          >
            <template v-if="messageItem.type === 'resume-report'">
              <ResumeReportCard :raw-report="messageItem.report" @open-fullscreen="openFullscreen" />
            </template>
            <template v-else>
              <div class="bubble">{{ messageItem.text }}</div>
              <div v-if="messageItem.meta" class="meta">{{ messageItem.meta }}</div>
            </template>
          </article>
        </div>
      </section>

      <footer class="composer-wrap">
        <div class="composer-console">
          <div class="composer">
            <div class="target-row">
              <select v-model="jobCategory" aria-label="岗位分类">
                <option value="tech">技术研发</option>
                <option value="ai">AI / 算法</option>
                <option value="data">数据岗位</option>
                <option value="product">产品运营</option>
                <option value="qa">测试质量</option>
              </select>
              <select v-model="targetPosition" aria-label="目标岗位">
                <option v-for="option in targetOptions" :key="option" :value="option">{{ option }}</option>
              </select>
            </div>
            <textarea
              v-model="composerText"
              placeholder="向面试助手发送消息，或上传简历 / 录音后让它自动调度 Agent。"
              @keydown.enter.exact.prevent="submitComposer"
            ></textarea>
            <div v-if="attachmentInfo" class="mounted-file" data-testid="mounted-file">
              <div class="mounted-file__type">{{ attachmentInfo.shortType }}</div>
              <div class="mounted-file__content">
                <strong>{{ attachmentInfo.name }}</strong>
                <span>{{ attachmentInfo.kind }} · {{ attachmentInfo.detail }} · 发送后处理</span>
              </div>
              <button type="button" class="mounted-file__clear" aria-label="移除已挂载文件" @click="clearAttachment">×</button>
            </div>
            <div class="composer-actions">
              <div class="attachments">
                <label class="file-label">
                  上传简历
                  <input ref="resumeInput" type="file" accept=".pdf,.docx,.png,.jpg,.jpeg" @change="handleResumeSelected" />
                </label>
                <label class="file-label">
                  上传录音
                  <input ref="audioInput" type="file" accept="audio/*,.mp3,.wav,.m4a" @change="handleAudioSelected" />
                </label>
                <button type="button" class="mini-button" @click="startMock">模拟面试</button>
                <button type="button" class="mini-button" @click="generateQuestions">练习题</button>
              </div>
              <button type="button" class="send" @click="submitComposer">发送</button>
            </div>
          </div>

          <div class="input-context" aria-label="分析上下文">
            <section class="jd-panel">
              <label for="jobDescription">可选：粘贴目标岗位 JD</label>
              <textarea
                id="jobDescription"
                v-model="jobDescription"
                placeholder="粘贴具体公司的岗位描述后，报告会生成 JD 匹配率、缺失项和拓扑图。"
              ></textarea>
              <p>不填写也可以分析，系统会使用上方选择的目标岗位画像。</p>
            </section>

            <section class="session-panel">
              <h3>当前会话</h3>
              <p>{{ sessionInfo }}</p>
            </section>
          </div>
        </div>
      </footer>
    </main>

    <aside class="side">
      <h2>Agent 快捷入口</h2>
      <div class="agent-list">
        <button type="button" @click="quickPrompt('请帮我分析简历，我会上传 PDF、DOCX 或图片简历。')">
          <strong>Resume Evaluation Agent</strong>
          <span>简历解析、多维评价、模板查重、违禁词检测、岗位适配。</span>
        </button>
        <button type="button" @click="startMock">
          <strong>Mock Interview Agent</strong>
          <span>多轮面试、智能追问、即时反馈和总结。</span>
        </button>
        <button type="button" @click="quickPrompt('我想上传真实面试录音做能力复盘。')">
          <strong>Audio Analysis Agent</strong>
          <span>语音转写、问题抽取、答案评估、真实题库沉淀。</span>
        </button>
        <button type="button" @click="generateQuestions">
          <strong>Question Generation Agent</strong>
          <span>基于简历、岗位、题库和宝典生成个性化练习题。</span>
        </button>
      </div>
    </aside>

    <ResumeReportFullscreen
      v-if="fullscreenReport"
      :raw-report="fullscreenReport"
      @close="fullscreenReport = null"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue";
import ResumeReportCard from "@/components/ResumeReportCard.vue";
import ResumeReportFullscreen from "@/components/ResumeReportFullscreen.vue";

const API = "http://127.0.0.1:8000";

const jobOptions = {
  tech: ["后端开发工程师", "前端开发工程师", "全栈开发工程师", "Java 开发工程师", "Python 开发工程师"],
  ai: ["AI算法工程师", "机器学习工程师", "深度学习工程师", "计算机视觉工程师", "自然语言处理工程师"],
  data: ["数据分析师", "数据开发工程师", "商业分析师", "数据科学家"],
  product: ["产品经理", "AI产品经理", "用户运营", "内容运营"],
  qa: ["测试工程师", "自动化测试工程师", "测试开发工程师", "质量工程师"],
};

const messages = ref([]);
const composerText = ref("");
const jobCategory = ref("ai");
const targetPosition = ref(jobOptions.ai[0]);
const jobDescription = ref("");
const pendingResumeFile = ref(null);
const pendingAudioFile = ref(null);
const sessionId = ref("");
const agentStatus = ref("Router Agent 待命");
const sessionInfo = ref("尚未开始模拟面试。上传简历后，练习题和面试问题会更贴合你的经历。");
const fullscreenReport = ref(null);
const messagesRef = ref(null);
const resumeInput = ref(null);
const audioInput = ref(null);

const targetOptions = computed(() => jobOptions[jobCategory.value] || jobOptions.tech);

const extensionOf = (file) => {
  const parts = file.name.split(".");
  if (parts.length > 1) return parts.at(-1).toUpperCase();
  return (file.type || "FILE").split("/").at(-1).toUpperCase();
};

const describeResumeFile = (file) => {
  const ext = extensionOf(file);
  if (ext === "PDF") return "PDF 简历";
  if (ext === "DOCX") return "DOCX 简历";
  if (["PNG", "JPG", "JPEG"].includes(ext)) return "图片简历";
  return `${ext} 文件`;
};

const describeAudioFile = (file) => {
  const ext = extensionOf(file);
  if (["MP3", "WAV", "M4A"].includes(ext)) return `${ext} 录音`;
  return file.type ? "音频文件" : `${ext} 文件`;
};

const attachmentInfo = computed(() => {
  if (pendingResumeFile.value) {
    const shortType = extensionOf(pendingResumeFile.value);
    return {
      name: pendingResumeFile.value.name,
      shortType,
      kind: "简历附件",
      detail: describeResumeFile(pendingResumeFile.value),
    };
  }
  if (pendingAudioFile.value) {
    const shortType = extensionOf(pendingAudioFile.value);
    return {
      name: pendingAudioFile.value.name,
      shortType,
      kind: "录音附件",
      detail: describeAudioFile(pendingAudioFile.value),
    };
  }
  return null;
});

watch(jobCategory, () => {
  targetPosition.value = targetOptions.value[0];
});

const addMessage = (role, text, meta = "") => {
  messages.value.push({ id: crypto.randomUUID(), type: "text", role, text, meta });
  scrollToBottom();
};

const addResumeReport = (report) => {
  messages.value.push({ id: crypto.randomUUID(), type: "resume-report", role: "assistant", report });
  scrollToBottom();
};

const scrollToBottom = async () => {
  await nextTick();
  if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight;
};

const setBusy = (label) => {
  agentStatus.value = label;
};

const quickPrompt = async (text) => {
  composerText.value = text;
  await sendChat();
};

const handleResumeSelected = (event) => {
  pendingResumeFile.value = event.target.files?.[0] || null;
  pendingAudioFile.value = null;
  if (audioInput.value) audioInput.value.value = "";
  if (pendingResumeFile.value) {
    setBusy("简历已挂载，等待你的分析需求");
    sessionInfo.value = "简历已挂载。请在对话框写明关注点，点击发送后生成可视化体检报告。";
  }
};

const handleAudioSelected = (event) => {
  pendingAudioFile.value = event.target.files?.[0] || null;
  pendingResumeFile.value = null;
  if (resumeInput.value) resumeInput.value.value = "";
  if (pendingAudioFile.value) {
    setBusy("录音已挂载，等待你的复盘需求");
    sessionInfo.value = "录音已挂载。你可以补充希望重点复盘的问题。";
  }
};

const clearAttachment = () => {
  pendingResumeFile.value = null;
  pendingAudioFile.value = null;
  if (resumeInput.value) resumeInput.value.value = "";
  if (audioInput.value) audioInput.value.value = "";
  setBusy("Router Agent 待命");
  sessionInfo.value = "已移除挂载文件。你可以重新上传简历或录音。";
};

const submitComposer = async () => {
  const text = composerText.value.trim();
  if (!text && !pendingResumeFile.value && !pendingAudioFile.value) return;
  if (sessionId.value) {
    addMessage("user", text);
    composerText.value = "";
    await sendAnswerToMock(text);
    return;
  }
  if (pendingResumeFile.value) {
    composerText.value = "";
    await uploadResume(text || `请分析这份简历，目标岗位是 ${targetPosition.value}。`);
    return;
  }
  if (pendingAudioFile.value) {
    composerText.value = "";
    await uploadAudio(text || "请复盘这段真实面试录音。");
    return;
  }
  await sendChat();
};

const newThread = () => {
  messages.value = [];
  sessionId.value = "";
  fullscreenReport.value = null;
  pendingResumeFile.value = null;
  pendingAudioFile.value = null;
  if (resumeInput.value) resumeInput.value.value = "";
  if (audioInput.value) audioInput.value.value = "";
  setBusy("Router Agent 待命");
  sessionInfo.value = "已开启新会话。上传简历后会生成可视化体检报告。";
};

const sendChat = async () => {
  const message = composerText.value.trim();
  if (!message) return;
  addMessage("user", message);
  composerText.value = "";
  setBusy("Router Agent 正在识别意图");
  try {
    const response = await fetch(`${API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, target_position: targetPosition.value }),
    });
    const data = await response.json();
    setBusy(`${data.intent || "Agent"} 已响应`);
    const payload = data.data && Object.keys(data.data).length ? `\n\n${JSON.stringify(data.data, null, 2)}` : "";
    addMessage("assistant", `${data.message}${payload}`, data.intent || "router");
  } catch {
    setBusy("连接失败");
    addMessage("assistant", "无法连接后端服务，请确认 FastAPI 已启动在 http://127.0.0.1:8000。");
  }
};

const uploadResume = async (userInstruction = "") => {
  const file = pendingResumeFile.value;
  if (!file) return;
  addMessage("user", `已上传简历：${file.name}\n目标岗位：${targetPosition.value}\n分析需求：${userInstruction}`);
  setBusy("Resume Evaluation Agent 正在分析");
  const form = new FormData();
  form.append("file", file);
  form.append("target_position", targetPosition.value);
  form.append("user_instruction", userInstruction);
  if (jobDescription.value.trim()) form.append("job_description", jobDescription.value.trim());

  try {
    const response = await fetch(`${API}/files/resume`, { method: "POST", body: form });
    const data = await response.json();
    setBusy("Resume Evaluation Agent 已完成");
    sessionInfo.value = `目标岗位：${data.job_fit?.target_position || targetPosition.value}；解析类型：${data.profile?.source_kind || "-"}；综合评分：${data.quality_score}；分析引擎：${data.analysis_engine || "rules"}`;
    addResumeReport(data);
  } catch {
    setBusy("简历分析失败");
    addMessage("assistant", "简历上传或分析失败，请检查后端服务和文件格式。");
  } finally {
    pendingResumeFile.value = null;
    if (resumeInput.value) resumeInput.value.value = "";
  }
};

const startMock = async () => {
  setBusy("Mock Interview Agent 正在准备");
  addMessage("user", "开始模拟面试");
  try {
    const response = await fetch(`${API}/interviews/mock/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_position: targetPosition.value }),
    });
    const data = await response.json();
    sessionId.value = data.session_id;
    setBusy("Mock Interview Agent 面试中");
    sessionInfo.value = `模拟面试会话：${sessionId.value}`;
    addMessage("assistant", data.question, `第 ${data.round_index} 轮`);
  } catch {
    setBusy("模拟面试启动失败");
    addMessage("assistant", "无法启动模拟面试，请确认后端服务已启动。");
  }
};

const sendAnswerToMock = async (answerText) => {
  if (!sessionId.value) {
    await startMock();
    return;
  }
  setBusy("Mock Interview Agent 正在追问");
  const response = await fetch(`${API}/interviews/mock/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId.value, answer: answerText }),
  });
  const data = await response.json();
  addMessage("assistant", `${data.feedback ? `${data.feedback}\n\n` : ""}${data.question}`, data.finished ? "面试结束" : `第 ${data.round_index} 轮`);
  setBusy(data.finished ? "Mock Interview Agent 已总结" : "Mock Interview Agent 面试中");
};

const uploadAudio = async (userInstruction = "") => {
  const file = pendingAudioFile.value;
  if (!file) return;
  addMessage("user", `已上传真实面试录音：${file.name}${userInstruction ? `\n复盘需求：${userInstruction}` : ""}`);
  setBusy("Audio Analysis Agent 正在创建任务");
  const form = new FormData();
  form.append("file", file);
  try {
    const response = await fetch(`${API}/interviews/audio`, { method: "POST", body: form });
    const data = await response.json();
    setBusy("Audio Analysis Agent 已接收");
    addMessage("assistant", `录音分析任务已创建。\n任务 ID：${data.id}\n状态：${data.status}\n你可以在 /tasks/${data.id} 查询进度。`, "audio-agent");
  } catch {
    setBusy("录音上传失败");
    addMessage("assistant", "录音上传失败，请检查后端服务。");
  } finally {
    pendingAudioFile.value = null;
    if (audioInput.value) audioInput.value.value = "";
  }
};

const generateQuestions = async () => {
  addMessage("user", "请生成个性化练习题");
  setBusy("Question Generation Agent 正在生成");
  const form = new FormData();
  form.append("target_position", targetPosition.value);
  try {
    const response = await fetch(`${API}/learning/questions`, { method: "POST", body: form });
    const data = await response.json();
    setBusy("Question Generation Agent 已完成");
    addMessage("assistant", `已生成练习题：\n${data.questions.map((q, index) => `${index + 1}. ${q.title}`).join("\n")}`, "question-agent");
  } catch {
    setBusy("练习题生成失败");
    addMessage("assistant", "练习题生成失败，请确认后端服务已启动。");
  }
};

const openFullscreen = (report) => {
  fullscreenReport.value = report;
};
</script>
