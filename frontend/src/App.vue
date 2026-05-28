<template>
  <div class="app-shell" :class="{ 'mock-layout': activeMode === 'mock' }">
    <nav class="rail" aria-label="主导航">
      <div class="mark">AI</div>
      <button type="button" class="rail-button" title="新会话" @click="newThread">+</button>
      <button type="button" class="rail-button" title="简历分析" @click="quickPrompt('请帮我分析简历，我会上传 PDF、DOCX 或图片简历。')">CV</button>
      <button type="button" class="rail-button" title="模拟面试" @click="startMock">MI</button>
      <button type="button" class="rail-button" title="练习题" @click="openPracticeFeed">Q</button>
    </nav>

    <main class="workspace">
      <header class="topbar">
        <div>
          <h1>智能面试助手</h1>
          <p>统一入口调度简历评估、模拟面试、录音复盘和练习题 Agent。</p>
        </div>
        <div class="status-pill"><span class="dot"></span>{{ agentStatus }}</div>
      </header>

      <section ref="messagesRef" class="messages">
        <button v-if="completedNotice" type="button" class="review-toast" data-testid="review-toast" @click="openReviewFromTask(completedNotice.task)">
          <strong>复盘已完成</strong>
          <span>{{ completedNotice.task.message || "点击进入复盘控制室" }}</span>
        </button>

        <TaskQueuePanel
          v-if="activeMode === 'chat' && tasks.length"
          class="task-queue-card"
          :tasks="tasks"
          @refresh="loadTasks"
          @open-review="openReviewFromTask"
        />

        <HolographicInterviewRoom
          v-if="activeMode === 'mock'"
          :session-id="sessionId"
          :target-position="targetPosition"
          :mode="mockMode"
          :transcript="mockTranscript"
          :current-turn="mockCurrentTurn"
          :draft="mockDraft"
          :mic-pressed="mockMicPressed"
          @mode-change="mockMode = $event"
          @draft-change="mockDraft = $event"
          @send="sendMockDraft"
          @finish="finishMock"
          @exit="exitMockRoom"
          @mic-placeholder="showMockMicPlaceholder"
        />

        <ReviewControlRoom
          v-else-if="activeMode === 'review' && activeReview"
          :review="activeReview"
          @annotate="submitAnnotation"
        />

        <LearningPracticeBoard
          v-else-if="activeMode === 'practice'"
          :questions="practiceQuestions"
          :insights="practiceInsights"
          :feedback-by-id="answerFeedback"
          :target-position="targetPosition"
          @submit-answer="submitPracticeAnswer"
          @voice-placeholder="showVoicePlaceholder"
        />

        <template v-else>
          <section v-if="messages.length === 0" class="hero">
            <h2>今天想先提升哪一块面试能力？</h2>
            <p>你可以先挂载文件再发送需求；录音复盘会进入异步任务队列。</p>
            <div class="suggestions">
              <button type="button" @click="quickPrompt('请帮我分析简历，目标岗位是后端开发工程师。')">
                <strong>分析简历</strong>
                <span>先挂载文件，再发送你的关注点。</span>
              </button>
              <button type="button" @click="startMock">
                <strong>开始模拟面试</strong>
                <span>进入全息面试舱，支持深挖追问。</span>
              </button>
              <button type="button" @click="quickPrompt('我想上传真实面试录音做复盘。')">
                <strong>复盘录音</strong>
                <span>任务队列、逐句诊断、讲师批注。</span>
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
        </template>
      </section>

      <footer v-if="activeMode !== 'mock'" class="composer-wrap">
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
                <span>{{ attachmentInfo.kind }} / {{ attachmentInfo.detail }} / 发送后处理</span>
              </div>
              <button type="button" class="mounted-file__clear" aria-label="移除已挂载文件" @click="clearAttachment">x</button>
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
                <button type="button" class="mini-button" @click="openPracticeFeed">练习题</button>
              </div>
              <button type="button" class="send" @click="submitComposer">发送</button>
            </div>
          </div>

          <div class="input-context" aria-label="分析上下文">
            <section class="jd-panel">
              <label for="jobDescription">可选：粘贴目标岗位 JD</label>
              <textarea id="jobDescription" v-model="jobDescription" placeholder="粘贴岗位描述后，简历报告会生成 JD 匹配诊断。"></textarea>
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

    <aside v-if="activeMode !== 'mock'" class="side">
      <div class="side-title-row">
        <h2>Agent 快捷入口</h2>
        <button type="button" class="teacher-chip" @click="loginAsTeacher">
          {{ currentUser ? currentUser.display_name : "讲师登录" }}
        </button>
      </div>
      <div class="agent-list">
        <button type="button" @click="quickPrompt('请帮我分析简历，我会上传 PDF、DOCX 或图片简历。')">
          <strong>Resume Evaluation Agent</strong>
          <span>简历解析、多维评价、岗位适配和可视化报告。</span>
        </button>
        <button type="button" @click="startMock">
          <strong>Mock Interview Agent</strong>
          <span>沉浸式面试舱、动态追问、压力仪表盘和能力总结。</span>
        </button>
        <button type="button" @click="quickPrompt('我想上传真实面试录音做能力复盘。')">
          <strong>Audio Analysis Agent</strong>
          <span>任务队列、声纹转写、RAG 诊断、讲师批注。</span>
        </button>
        <button type="button" @click="openPracticeFeed">
          <strong>Question Generation Agent</strong>
          <span>RAG 题库、瀑布流推荐、错题本和技能树。</span>
        </button>
      </div>
    </aside>

    <ResumeReportFullscreen v-if="fullscreenReport" :raw-report="fullscreenReport" @close="fullscreenReport = null" />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import HolographicInterviewRoom from "@/components/HolographicInterviewRoom.vue";
import LearningPracticeBoard from "@/components/LearningPracticeBoard.vue";
import ResumeReportCard from "@/components/ResumeReportCard.vue";
import ResumeReportFullscreen from "@/components/ResumeReportFullscreen.vue";
import ReviewControlRoom from "@/components/ReviewControlRoom.vue";
import TaskQueuePanel from "@/components/TaskQueuePanel.vue";

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
const sessionInfo = ref("尚未开始任务。上传录音后，任务队列会自动刷新复盘进度。");
const fullscreenReport = ref(null);
const messagesRef = ref(null);
const resumeInput = ref(null);
const audioInput = ref(null);
const activeMode = ref("chat");
const practiceQuestions = ref([]);
const practiceInsights = ref([]);
const answerFeedback = ref({});
const lastPracticeScore = ref(null);
const authToken = ref("");
const currentUser = ref(null);
const tasks = ref([]);
const activeReview = ref(null);
const taskPoller = ref(null);
const completedNotice = ref(null);
const mockMode = ref("project_deep_dive");
const mockTranscript = ref([]);
const mockCurrentTurn = ref(null);
const mockDraft = ref("");
const mockMicPressed = ref(false);

const targetOptions = computed(() => jobOptions[jobCategory.value] || jobOptions.tech);

watch(jobCategory, () => {
  targetPosition.value = targetOptions.value[0];
});

const authHeaders = () => (authToken.value ? { Authorization: `Bearer ${authToken.value}` } : {});

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
  if (pendingResumeFile.value) return { name: pendingResumeFile.value.name, shortType: extensionOf(pendingResumeFile.value), kind: "简历附件", detail: describeResumeFile(pendingResumeFile.value) };
  if (pendingAudioFile.value) return { name: pendingAudioFile.value.name, shortType: extensionOf(pendingAudioFile.value), kind: "录音附件", detail: describeAudioFile(pendingAudioFile.value) };
  return null;
});

const addMessage = (role, text, meta = "") => {
  activeMode.value = "chat";
  messages.value.push({ id: crypto.randomUUID(), type: "text", role, text, meta });
  scrollToBottom();
};

const addResumeReport = (report) => {
  activeMode.value = "chat";
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

const responseToTurn = (data) => ({
  session_id: data.session_id,
  question: data.question,
  feedback: data.feedback,
  round_index: data.round_index || 1,
  round_total: data.round_total || 8,
  state: data.state || "NewQuestion",
  mode: data.mode || mockMode.value,
  question_type: data.question_type || "project",
  phase_label: data.phase_label || "",
  anchor_project: data.anchor_project || "",
  difficulty_level: data.difficulty_level || "",
  question_intent: data.question_intent || "",
  probing_reason: data.probing_reason || "",
  detected_keywords: data.detected_keywords || [],
  pressure_level: data.pressure_level || 35,
  answer_depth_score: data.answer_depth_score || 0,
  skill_scores: data.skill_scores || {},
  reverse_question_prompt: data.reverse_question_prompt || "",
  final_report: data.final_report || null,
  finished: data.finished || false,
});

const loginAsTeacher = async () => {
  const response = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "teacher", password: "teacher123" }),
  });
  const data = await response.json();
  authToken.value = data.token;
  currentUser.value = data.user;
  setBusy("讲师已登录");
  await loadTasks();
  startTaskPolling();
};

const quickPrompt = async (text) => {
  activeMode.value = "chat";
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
    sessionInfo.value = "录音已挂载。发送后会进入异步任务队列，不会阻塞当前页面。";
  }
};

const clearAttachment = () => {
  pendingResumeFile.value = null;
  pendingAudioFile.value = null;
  if (resumeInput.value) resumeInput.value.value = "";
  if (audioInput.value) audioInput.value.value = "";
  setBusy("Router Agent 待命");
};

const submitComposer = async () => {
  const text = composerText.value.trim();
  if (!text && !pendingResumeFile.value && !pendingAudioFile.value) return;
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
  if (sessionId.value && activeMode.value !== "mock") {
    mockDraft.value = text;
    composerText.value = "";
    activeMode.value = "mock";
    await sendMockDraft();
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
  activeMode.value = "chat";
  activeReview.value = null;
  completedNotice.value = null;
  mockTranscript.value = [];
  mockCurrentTurn.value = null;
  mockDraft.value = "";
  if (resumeInput.value) resumeInput.value.value = "";
  if (audioInput.value) audioInput.value.value = "";
  setBusy("Router Agent 待命");
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
    if (data.intent === "mock_interview") {
      await startMock();
      return;
    }
    if (data.intent === "learning_resource" && data.data?.questions) {
      practiceQuestions.value = data.data.questions;
      activeMode.value = "practice";
      await loadPracticeFeed();
      return;
    }
    addMessage("assistant", data.message, data.intent || "router");
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
    sessionInfo.value = `目标岗位：${data.job_fit?.target_position || targetPosition.value}；综合评分：${data.quality_score}`;
    addResumeReport(data);
  } catch {
    setBusy("简历分析失败");
    addMessage("assistant", "简历上传或分析失败，请检查后端服务和文件格式。");
  } finally {
    pendingResumeFile.value = null;
    if (resumeInput.value) resumeInput.value.value = "";
  }
};

const uploadAudio = async (userInstruction = "") => {
  const file = pendingAudioFile.value;
  if (!file) return;
  addMessage("user", `已上传真实面试录音：${file.name}${userInstruction ? `\n复盘需求：${userInstruction}` : ""}`);
  setBusy("Audio Analysis Agent 正在创建异步任务");
  const form = new FormData();
  form.append("file", file);
  form.append("user_id", currentUser.value?.id || "demo-user");
  try {
    const response = await fetch(`${API}/interviews/audio`, { method: "POST", headers: authHeaders(), body: form });
    const data = await response.json();
    tasks.value = [data, ...tasks.value.filter((task) => task.id !== data.id)];
    startTaskPolling();
    setBusy("Audio Analysis Agent 已接收");
    addMessage("assistant", `录音已接收，正在呼叫音频解析 Agent 进行声纹分离与知识点比对，这大约需要 2-3 分钟，请先喝杯水或进行其他练习。\n任务 ID：${data.id}`, "audio-agent");
    sessionInfo.value = "复盘任务已进入队列。处理完成后会自动弹出通知。";
  } catch {
    setBusy("录音上传失败");
    addMessage("assistant", "录音上传失败，请检查后端服务。");
  } finally {
    pendingAudioFile.value = null;
    if (audioInput.value) audioInput.value.value = "";
  }
};

const loadTasks = async () => {
  if (!authToken.value) return;
  const previous = new Map(tasks.value.map((task) => [task.id, task]));
  const response = await fetch(`${API}/tasks`, { headers: authHeaders() });
  const data = await response.json();
  const nextTasks = data.tasks || [];
  const newlyCompleted = nextTasks.find((task) => {
    const oldTask = previous.get(task.id);
    return task.status === "completed" && task.review_report_id && oldTask?.status !== "completed";
  });
  tasks.value = nextTasks;
  if (newlyCompleted && activeMode.value !== "review") {
    completedNotice.value = { task: newlyCompleted };
    setBusy("复盘已完成，点击通知进入控制室");
  }
  if (nextTasks.some((task) => ["pending", "running"].includes(task.status))) startTaskPolling();
  else stopTaskPolling();
};

const openReviewFromTask = async (task) => {
  if (!task.review_report_id) {
    setBusy("任务仍在处理中");
    return;
  }
  const response = await fetch(`${API}/reviews/${task.review_report_id}`, { headers: authHeaders() });
  const data = await response.json();
  activeReview.value = data.review;
  activeMode.value = "review";
  if (completedNotice.value?.task?.id === task.id) completedNotice.value = null;
  setBusy("复盘控制室已打开");
};

const startTaskPolling = () => {
  if (!authToken.value || taskPoller.value) return;
  taskPoller.value = window.setInterval(loadTasks, 3000);
};

const stopTaskPolling = () => {
  if (!taskPoller.value) return;
  window.clearInterval(taskPoller.value);
  taskPoller.value = null;
};

const submitAnnotation = async (payload) => {
  if (!activeReview.value) return;
  const response = await fetch(`${API}/reviews/${activeReview.value.id}/annotations`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  activeReview.value = {
    ...activeReview.value,
    annotations: [...(activeReview.value.annotations || []), data.annotation],
  };
  setBusy("讲师批注已保存");
};

const startMock = async () => {
  activeMode.value = "mock";
  setBusy("Mock Interview Agent 正在准备面试舱");
  try {
    const response = await fetch(`${API}/interviews/mock/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: "demo-user", target_position: targetPosition.value, mode: mockMode.value }),
    });
    const data = await response.json();
    sessionId.value = data.session_id;
    mockCurrentTurn.value = responseToTurn(data);
    mockTranscript.value = [{ id: crypto.randomUUID(), role: "assistant", text: data.question }];
    sessionInfo.value = `沉浸式模拟面试进行中：${targetPosition.value}`;
    setBusy("Mock Interview Agent 面试中");
  } catch {
    setBusy("模拟面试启动失败");
  }
};

const sendMockDraft = async () => {
  const answerText = mockDraft.value.trim();
  if (mockCurrentTurn.value?.finished) return;
  if (!answerText || !sessionId.value) return;
  mockTranscript.value.push({ id: crypto.randomUUID(), role: "user", text: answerText });
  mockDraft.value = "";
  setBusy("Mock Interview Agent 正在决策追问");
  const response = await fetch(`${API}/interviews/mock/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId.value, answer: answerText }),
  });
  const data = await response.json();
  mockCurrentTurn.value = responseToTurn(data);
  mockTranscript.value.push({ id: crypto.randomUUID(), role: "assistant", text: `${data.feedback ? `${data.feedback}\n` : ""}${data.question}` });
  setBusy(data.finished ? "Mock Interview Agent 已总结" : `Mock Interview Agent ${data.state || "追问中"}`);
};

const finishMock = async () => {
  if (!sessionId.value) {
    activeMode.value = "chat";
    return;
  }
  if (mockCurrentTurn.value?.finished) return;
  setBusy("Mock Interview Agent 正在生成即时复盘");
  try {
    const response = await fetch(`${API}/interviews/mock/finish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId.value, reason: "user_requested" }),
    });
    const data = await response.json();
    mockDraft.value = "";
    mockCurrentTurn.value = responseToTurn(data);
    mockTranscript.value.push({ id: crypto.randomUUID(), role: "assistant", text: `${data.feedback ? `${data.feedback}\n` : ""}${data.question}` });
    setBusy("Mock Interview Agent 已总结");
  } catch {
    setBusy("结束面试失败，请稍后重试");
  }
};

const exitMockRoom = () => {
  activeMode.value = "chat";
  setBusy("Router Agent 待命");
};

const showMockMicPlaceholder = (pressed) => {
  mockMicPressed.value = pressed;
  setBusy(pressed ? "麦克风为 UI 占位，真实语音识别待接入" : "Mock Interview Agent 面试中");
};

const openPracticeFeed = async () => {
  setBusy("Question Generation Agent 正在推荐");
  activeMode.value = "practice";
  await loadPracticeFeed();
};

const loadPracticeFeed = async () => {
  const response = await fetch(`${API}/learning/feed`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: "demo-user", target_position: targetPosition.value, limit: 8, last_answer_score: lastPracticeScore.value }),
  });
  const data = await response.json();
  practiceQuestions.value = data.questions || [];
  practiceInsights.value = data.insights || [];
  setBusy("Question Generation Agent 已生成练习场");
};

const submitPracticeAnswer = async (question, answerText) => {
  const response = await fetch(`${API}/learning/answers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: "demo-user", question_id: question.id, answer_text: answerText, answer_mode: "text", target_position: targetPosition.value }),
  });
  const data = await response.json();
  answerFeedback.value = { ...answerFeedback.value, [question.id]: data.feedback };
  lastPracticeScore.value = data.feedback.score;
};

const showVoicePlaceholder = () => {
  setBusy("语音作答待接入真实语音识别");
};

const openFullscreen = (report) => {
  fullscreenReport.value = report;
};

onBeforeUnmount(() => {
  stopTaskPolling();
});
</script>
