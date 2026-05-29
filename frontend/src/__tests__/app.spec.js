import { mount, flushPromises } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App.vue";

vi.mock("echarts", () => ({
  init: vi.fn(() => ({ setOption: vi.fn(), dispose: vi.fn() })),
}));

const resumeReport = {
  quality_score: 86,
  needs_user_confirmation: false,
  analysis_engine: "llm",
  template_similarity_score: 8,
  forbidden_words: [],
  profile: { source_kind: "docx", skills: ["Python", "PyTorch"], projects: ["模型训练"], parse_confidence: 0.9 },
  dimension_scores: { 专业技能: 88, 项目经验: 84 },
  job_fit: { target_position: "AI算法工程师", fit_score: 80, expected_skills: ["Python"], matched_skills: ["Python"], missing_skills: [] },
  jd_diagnosis: { enabled: false, matched_items: [], missing_items: [], suggestions: [] },
  interview_risks: [{ risk_point: "模型评估", question: "请解释评估指标。", severity: "medium" }],
  logic_gaps: [],
  reading_experience: { signal_to_noise_score: 82 },
  star_optimizations: [{ before: "做项目", after: "补充量化结果", action_note: "补齐 STAR" }],
  recommendations: ["补充量化结果"],
};

const feedPayload = {
  questions: [
    {
      id: "q1",
      title: "PyTorch 训练效果怎么排查？",
      prompt: "请从数据、模型、损失函数和评估指标中选择两项说明排查路径。",
      answer_reference: "说明场景、模型、训练、评估和结果。",
      source: "generated",
      position: "AI算法工程师",
      skill_tags: ["PyTorch"],
      difficulty: "medium",
      occurrence_count: 1,
    },
  ],
  insights: [{ skill: "PyTorch", mastery: 20, attempts: 0, status: "locked" }],
  rag_status: {
    chunks: 4,
    provider: "local",
    retrieved: 2,
    sources: [{ title: "Redis 缓存", repo: "internal/local-rag-seed", license: "internal" }],
  },
  profile_used: true,
  profile_summary: {
    available: true,
    target_position: "AI算法工程师",
    skills: ["Python", "PyTorch"],
    project_count: 1,
    internship_count: 0,
    parse_confidence: 0.9,
    quality_score: 86,
    needs_user_confirmation: false,
  },
};

const plannerChatPayload = {
  intent: "agent_plan",
  message: "Agent 已规划 5 步，已完成 5 步。已生成 1 道练习题，可直接进入练习。",
  data: {
    traces: [
      { tool_name: "classify_intent", status: "completed", summary: "识别到意图：learning_resource。" },
      { tool_name: "get_resume_profile", status: "completed", summary: "已读取简历画像，技能线索 2 项。" },
      { tool_name: "generate_learning_feed", status: "completed", summary: "已生成 1 道练习题推荐。" },
    ],
    questions: feedPayload.questions,
    insights: feedPayload.insights,
    rag_status: feedPayload.rag_status,
  },
};

const reviewPayload = {
  id: "review-1",
  task_id: "task-1",
  owner_user_id: "teacher-demo",
  audio_filename: "interview.wav",
  summary: "系统已完成逐句转写和 RAG 漏点诊断。",
  dimension_scores: { 准确度: 82, 流畅度: 76, 自信度: 70 },
  segments: [
    {
      id: "seg-system",
      speaker: "system",
      text: "复盘控制室已准备就绪，期待您的真实录音上传分析。",
      start_ms: 0,
      end_ms: 1500,
      confidence: 0.45,
    },
    {
      id: "seg-1",
      speaker: "interviewer",
      text: "说说你对 Spring Boot 自动装配的理解。",
      start_ms: 0,
      end_ms: 5000,
      confidence: 0.9,
      captured_question_id: "real-1",
      captured_question_title: "说说你对 Spring Boot 自动装配的理解。",
    },
    { id: "seg-2", speaker: "student", text: "主要是 starter 和自动配置类。", start_ms: 5000, end_ms: 12000, confidence: 0.86 },
  ],
  rag_diagnostics: [
    {
      segment_id: "seg-1",
      question: "说说你对 Spring Boot 自动装配的理解。",
      ideal_outline: ["starter", "条件装配", "配置绑定"],
      hit_points: ["starter"],
      missing_points: ["条件装配", "配置绑定"],
      correction_advice: "建议补齐红色漏点。",
    },
  ],
  annotations: [],
  captured_questions: [{ question_id: "real-1", title: "说说你对 Spring Boot 自动装配的理解。", skill_tags: ["Spring"], source_segment_id: "seg-1" }],
  acoustic_points: [{ time_ms: 5000, speech_rate: 132, filler_count: 0, emotion: "steady" }],
  growth_suggestions: ["补齐条件装配。"],
};

const mockStartPayload = {
  session_id: "mock-session-1",
  question: "我注意到你有模型训练项目。请讲清楚你的职责和最难的工程问题。",
  feedback: "已进入项目深挖模式。",
  round_index: 1,
  finished: false,
  state: "Greeting",
  mode: "project_deep_dive",
  question_type: "project",
  anchor_project: "模型训练：负责 PyTorch 训练和效果评估。",
  resume_context_used: true,
  resume_context_summary: "已读取简历画像，1 个项目 / 0 段实习，技能：Python、PyTorch",
  pressure_level: 38,
  answer_depth_score: 0,
  skill_scores: { 专业深度: 50, 项目表达: 50, 临场应变: 50 },
  detected_keywords: [],
};

const mockMessagePayload = {
  session_id: "mock-session-1",
  question: "你提到 PyTorch，请继续说明训练瓶颈和指标验证方式。",
  feedback: "回答基本完整，但需要补充量化结果。",
  round_index: 2,
  finished: false,
  state: "Probing",
  mode: "project_deep_dive",
  question_type: "project",
  probing_reason: "回答中出现了可深挖的技术关键词。",
  detected_keywords: ["PyTorch", "模型"],
  pressure_level: 67,
  answer_depth_score: 72,
  skill_scores: { 专业深度: 72, 项目表达: 70, 临场应变: 58 },
};

const mockFinishPayload = {
  session_id: "mock-session-1",
  question: "本轮沉浸式模拟面试已结束。你可以查看右侧能力图谱，并选择继续练习薄弱项。",
  feedback: "本轮提前结束，基于已完成 1/8 个回合评估。本轮模拟面试综合表现 62 分。",
  round_index: 2,
  round_total: 8,
  finished: true,
  state: "Closing",
  mode: "project_deep_dive",
  question_type: "summary",
  phase_label: "项目基础",
  pressure_level: 20,
  answer_depth_score: 0,
  detected_keywords: [],
  skill_scores: { 专业深度: 62, 项目表达: 60, 临场应变: 58 },
  final_report: {
    summary: "本轮提前结束，基于已完成 1/8 个回合评估。本轮模拟面试综合表现 62 分。",
    dimension_scores: { 专业深度: 62, 项目表达: 60, 临场应变: 58 },
    strengths: ["能够围绕问题展开回答"],
    weaknesses: ["量化表达"],
    practice_suggestions: ["继续练习项目复盘"],
  },
};

const okResponse = (payload) => ({ json: vi.fn(async () => payload) });
let resumeUploadShouldFail = false;
let feedShouldFail = false;
let feedPayloadOverride = null;

describe("App workflows", () => {
  let taskPollCount;

  beforeEach(() => {
    taskPollCount = 0;
    resumeUploadShouldFail = false;
    feedShouldFail = false;
    feedPayloadOverride = null;
    vi.useFakeTimers();
    vi.stubGlobal("crypto", { randomUUID: vi.fn(() => Math.random().toString(16).slice(2)) });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url, options = {}) => {
        if (url.endsWith("/auth/login")) return okResponse({ token: "teacher-token", user: { id: "teacher-demo", username: "teacher", role: "teacher", display_name: "讲师 Demo" } });
        if (url.endsWith("/auth/logout")) return okResponse({ ok: true });
        if (url.endsWith("/tasks")) {
          taskPollCount += 1;
          if (taskPollCount <= 1) return okResponse({ tasks: [] });
          if (taskPollCount === 2) return okResponse({ tasks: [{ id: "task-1", status: "running", stage: "transcribing", progress: 50, message: "正在转写", review_report_id: null }] });
          return okResponse({ tasks: [{ id: "task-1", status: "completed", stage: "ready_for_review", progress: 100, message: "录音复盘完成。", review_report_id: "review-1" }] });
        }
        if (url.endsWith("/chat")) {
          const body = options.body ? JSON.parse(options.body) : {};
          if (body.message?.includes("规划")) return okResponse(plannerChatPayload);
          return okResponse({ intent: "general_chat", message: "你好，我可以帮你分析简历。" });
        }
        if (url.endsWith("/files/resume")) {
          if (resumeUploadShouldFail) throw new Error("resume failed");
          return okResponse(resumeReport);
        }
        if (url.endsWith("/interviews/mock/start")) return okResponse(mockStartPayload);
        if (url.endsWith("/interviews/mock/message")) return okResponse(mockMessagePayload);
        if (url.endsWith("/interviews/mock/finish")) return okResponse(mockFinishPayload);
        if (url.endsWith("/learning/feed")) {
          if (feedShouldFail) throw new Error("feed failed");
          return okResponse(feedPayloadOverride || feedPayload);
        }
        if (url.endsWith("/learning/answers")) {
          return okResponse({ feedback: { question_id: "q1", score: 72, passed: true, highlights: ["覆盖了技术点"], improvements: ["补充结果指标"], senior_answer: "说明方案取舍。", next_difficulty: "medium", source: "rules" } });
        }
        if (url.endsWith("/interviews/audio")) return okResponse({ id: "task-1", status: "running", stage: "queued", progress: 10, message: "录音已接收。", review_report_id: null });
        if (url.endsWith("/reviews/review-1")) return okResponse({ review: reviewPayload });
        if (url.endsWith("/reviews/review-1/annotations")) return okResponse({ annotation: { id: "ann-1", review_id: "review-1", segment_id: "seg-1", author_name: "讲师 Demo", body: "补充条件装配。", created_at: "now" } });
        if (url.endsWith("/reviews/review-1/segments/seg-1")) return okResponse({ segment: { ...reviewPayload.segments[1], teacher_score: 88, speaker: "interviewer" } });
        throw new Error(`unexpected url: ${url}`);
      }),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not analyze when selecting resume, then renders visual report after send", async () => {
    const wrapper = mount(App, { attachTo: document.body });
    const resumeInput = wrapper.find('input[accept=".pdf,.docx,.png,.jpg,.jpeg"]');
    Object.defineProperty(resumeInput.element, "files", {
      value: [new File(["demo"], "resume.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" })],
      configurable: true,
    });

    await resumeInput.trigger("change");
    expect(fetch).not.toHaveBeenCalledWith(expect.stringContaining("/files/resume"), expect.anything());
    expect(wrapper.find('[data-testid="mounted-file"]').text()).toContain("resume.docx");
    await wrapper.find("textarea[placeholder]").setValue("请重点优化项目经历。");
    await wrapper.find(".send").trigger("click");
    await flushPromises();

    expect(fetch.mock.calls.find(([url]) => url.endsWith("/files/resume"))).toBeTruthy();
    expect(wrapper.find('[data-testid="resume-report-card"]').exists()).toBe(true);
  });

  it("reuses analyzed resume when starting mock interview without another upload", async () => {
    const wrapper = mount(App, { attachTo: document.body });
    const resumeInput = wrapper.find('input[accept=".pdf,.docx,.png,.jpg,.jpeg"]');
    Object.defineProperty(resumeInput.element, "files", {
      value: [new File(["demo"], "resume.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" })],
      configurable: true,
    });

    await resumeInput.trigger("change");
    await wrapper.find("textarea[placeholder]").setValue("请先分析这份简历。");
    await wrapper.find(".send").trigger("click");
    await flushPromises();
    const uploadCallsBeforeMock = fetch.mock.calls.filter(([url]) => url.endsWith("/files/resume")).length;

    const mockButton = wrapper.findAll(".mini-button").find((button) => button.text() === "模拟面试");
    await mockButton.trigger("click");
    await flushPromises();

    expect(fetch.mock.calls.filter(([url]) => url.endsWith("/files/resume")).length).toBe(uploadCallsBeforeMock);
    expect(fetch.mock.calls.find(([url]) => url.endsWith("/interviews/mock/start"))).toBeTruthy();
    expect(wrapper.find('[data-testid="interview-room"]').text()).toContain("锚定经历");
  });

  it("reuses analyzed resume for practice feed without reuploading", async () => {
    const wrapper = mount(App, { attachTo: document.body });
    const resumeInput = wrapper.find('input[accept=".pdf,.docx,.png,.jpg,.jpeg"]');
    Object.defineProperty(resumeInput.element, "files", {
      value: [new File(["demo"], "resume.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" })],
      configurable: true,
    });

    await resumeInput.trigger("change");
    await wrapper.find("textarea[placeholder]").setValue("请先分析这份简历。");
    await wrapper.find(".send").trigger("click");
    await flushPromises();
    const uploadCallsBeforePractice = fetch.mock.calls.filter(([url]) => url.endsWith("/files/resume")).length;

    const practiceButton = wrapper.findAll(".mini-button").find((button) => button.text() === "练习题");
    await practiceButton.trigger("click");
    await flushPromises();

    expect(fetch.mock.calls.filter(([url]) => url.endsWith("/files/resume")).length).toBe(uploadCallsBeforePractice);
    expect(fetch.mock.calls.find(([url]) => url.endsWith("/learning/feed"))).toBeTruthy();
    expect(wrapper.find('[data-testid="practice-board"]').text()).toContain("已基于上次简历画像");
  });

  it("renders planner trace from chat and keeps generated questions on practice board", async () => {
    const wrapper = mount(App);

    await wrapper.find("textarea[placeholder]").setValue("请根据我的简历规划 AI 面试练习计划");
    await wrapper.find(".send").trigger("click");
    await flushPromises();

    expect(fetch.mock.calls.find(([url]) => url.endsWith("/chat"))).toBeTruthy();
    expect(wrapper.classes()).toContain("practice-layout");
    expect(wrapper.find('[data-testid="planner-trace"]').text()).toContain("generate_learning_feed");
    expect(wrapper.find('[data-testid="practice-board"]').text()).toContain("PyTorch 训练效果怎么排查？");
  });

  it("opens holographic mock room and sends answers to mock endpoint with mode", async () => {
    const wrapper = mount(App);
    const mockButton = wrapper.findAll(".mini-button").find((button) => button.text() === "模拟面试");
    await mockButton.trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="interview-room"]').exists()).toBe(true);
    const startCall = fetch.mock.calls.find(([url]) => url.endsWith("/interviews/mock/start"));
    expect(JSON.parse(startCall[1].body).mode).toBe("project_deep_dive");

    await wrapper.find(".interview-deck textarea").setValue("我负责 PyTorch 模型训练，并用准确率和推理耗时验证效果。");
    await wrapper.find(".interview-deck .send").trigger("click");
    await flushPromises();

    expect(fetch.mock.calls.at(-1)[0]).toContain("/interviews/mock/message");
    expect(wrapper.find('[data-testid="interview-room"]').text()).toContain("PyTorch");
    expect(wrapper.find(".pressure-panel").text()).toContain("67%");
  });

  it("finishes mock interview through finish endpoint and shows final report", async () => {
    const wrapper = mount(App);
    const mockButton = wrapper.findAll(".mini-button").find((button) => button.text() === "模拟面试");
    await mockButton.trigger("click");
    await flushPromises();

    await wrapper.find(".interview-deck .danger-command").trigger("click");
    await flushPromises();

    const finishCall = fetch.mock.calls.find(([url]) => url.endsWith("/interviews/mock/finish"));
    expect(finishCall).toBeTruthy();
    expect(fetch.mock.calls.find(([url]) => url.endsWith("/interviews/mock/message"))).toBeFalsy();
    expect(wrapper.find('[data-testid="interview-final"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="interview-final"]').text()).toContain("本轮提前结束");
    expect(wrapper.find(".interview-deck textarea").attributes("disabled")).toBeDefined();
    expect(wrapper.find(".interview-deck .send").attributes("disabled")).toBeDefined();
  });

  it("prioritizes mounted resume over existing mock session when sending", async () => {
    const wrapper = mount(App);
    await wrapper.findAll(".mini-button")[0].trigger("click");
    await flushPromises();
    await wrapper.find(".ghost-command").trigger("click");
    await flushPromises();

    const resumeInput = wrapper.find('input[accept=".pdf,.docx,.png,.jpg,.jpeg"]');
    Object.defineProperty(resumeInput.element, "files", {
      value: [new File(["demo"], "resume.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" })],
      configurable: true,
    });
    await resumeInput.trigger("change");
    await wrapper.find("textarea[placeholder]").setValue("请帮我分析优化一下这个简历");
    await wrapper.find(".composer .send").trigger("click");
    await flushPromises();

    expect(fetch.mock.calls.find(([url]) => url.endsWith("/files/resume"))).toBeTruthy();
    expect(fetch.mock.calls.find(([url]) => url.endsWith("/interviews/mock/message"))).toBeFalsy();
    expect(wrapper.find('[data-testid="resume-report-card"]').exists()).toBe(true);
  });

  it("opens practice waterfall and submits an answer with target position", async () => {
    const wrapper = mount(App);
    const practiceButton = wrapper.findAll(".mini-button").find((button) => button.text() === "练习题");
    await practiceButton.trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="practice-board"]').exists()).toBe(true);
    expect(wrapper.classes()).toContain("practice-layout");
    expect(wrapper.find(".composer-wrap").classes()).toContain("practice-drawer");
    expect(wrapper.find(".composer-wrap").classes()).toContain("closed");
    expect(wrapper.find(".practice-drawer-tab").exists()).toBe(true);
    expect(wrapper.find(".practice-drawer-tab").attributes("aria-expanded")).toBe("false");
    await wrapper.find(".practice-drawer-tab").trigger("click");
    await flushPromises();
    expect(wrapper.find(".composer-wrap").classes()).toContain("open");
    expect(wrapper.find(".practice-drawer-tab").attributes("aria-expanded")).toBe("true");
    expect(wrapper.find(".practice-drawer .target-row").exists()).toBe(true);
    expect(wrapper.find(".practice-drawer textarea[placeholder]").exists()).toBe(true);
    expect(wrapper.find(".practice-drawer .send").exists()).toBe(true);
    expect(wrapper.find('[data-testid="practice-board"]').text()).toContain("本地 RAG 已命中 2 条知识片段");
    expect(wrapper.find(".qa-card h3").text()).toBe("PyTorch 训练效果怎么排查？");
    expect(wrapper.find(".question-prompt").text()).toContain("数据、模型");
    await wrapper.find(".qa-card textarea").setValue("我使用 PyTorch 训练并评估模型。");
    await wrapper.find(".qa-card .send").trigger("click");
    await flushPromises();

    const answerCall = fetch.mock.calls.find(([url]) => url.endsWith("/learning/answers"));
    expect(JSON.parse(answerCall[1].body).target_position).toBe("AI算法工程师");
    expect(wrapper.find('[data-testid="answer-feedback"]').text()).toContain("72");
  });

  it("builds practice profile from mounted resume before opening feed", async () => {
    const wrapper = mount(App);
    const resumeInput = wrapper.find('input[accept=".pdf,.docx,.png,.jpg,.jpeg"]');
    Object.defineProperty(resumeInput.element, "files", {
      value: [new File(["demo"], "resume.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" })],
      configurable: true,
    });
    await resumeInput.trigger("change");

    const practiceButton = wrapper.findAll(".mini-button").find((button) => button.text() === "练习题");
    await practiceButton.trigger("click");
    await flushPromises();

    const resumeIndex = fetch.mock.calls.findIndex(([url]) => url.endsWith("/files/resume"));
    const feedIndex = fetch.mock.calls.findIndex(([url]) => url.endsWith("/learning/feed"));
    expect(resumeIndex).toBeGreaterThan(-1);
    expect(feedIndex).toBeGreaterThan(resumeIndex);
    expect(wrapper.find('[data-testid="mounted-file"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="practice-board"]').text()).toContain("已基于当前简历");
  });

  it("keeps mounted resume and does not open fake personalized practice when resume profiling fails", async () => {
    resumeUploadShouldFail = true;
    const wrapper = mount(App);
    const resumeInput = wrapper.find('input[accept=".pdf,.docx,.png,.jpg,.jpeg"]');
    Object.defineProperty(resumeInput.element, "files", {
      value: [new File(["demo"], "resume.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" })],
      configurable: true,
    });
    await resumeInput.trigger("change");

    const practiceButton = wrapper.findAll(".mini-button").find((button) => button.text() === "练习题");
    await practiceButton.trigger("click");
    await flushPromises();

    expect(fetch.mock.calls.find(([url]) => url.endsWith("/learning/feed"))).toBeFalsy();
    expect(wrapper.find('[data-testid="mounted-file"]').text()).toContain("resume.docx");
    expect(wrapper.find('[data-testid="practice-board"]').exists()).toBe(false);
  });

  it("shows practice feed error state instead of staying in recommending status", async () => {
    feedShouldFail = true;
    const wrapper = mount(App);
    const practiceButton = wrapper.findAll(".mini-button").find((button) => button.text() === "练习题");
    await practiceButton.trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="practice-board"]').text()).toContain("练习推荐没有生成成功");
    expect(wrapper.find('[data-testid="practice-board"]').text()).toContain("练习推荐失败，请稍后重试。");
    expect(wrapper.find(".status-pill").text()).toContain("练习推荐失败");
  });

  it("shows empty practice state when feed returns no questions", async () => {
    feedPayloadOverride = { ...feedPayload, questions: [], rag_status: { chunks: 4, provider: "local", retrieved: 0, sources: [] } };
    const wrapper = mount(App);
    const practiceButton = wrapper.findAll(".mini-button").find((button) => button.text() === "练习题");
    await practiceButton.trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="practice-board"]').text()).toContain("暂时没有匹配到练习卡");
    expect(wrapper.find(".status-pill").text()).toContain("暂无推荐题");
  });

  it("polls audio task, shows completion toast, and opens review control room", async () => {
    const wrapper = mount(App);
    expect(wrapper.find('[data-testid="task-queue"]').exists()).toBe(false);

    await wrapper.find(".teacher-chip").trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="task-queue"]').exists()).toBe(false);

    const audioInput = wrapper.find('input[accept="audio/*,.mp3,.wav,.m4a"]');
    Object.defineProperty(audioInput.element, "files", {
      value: [new File(["demo"], "interview.wav", { type: "audio/wav" })],
      configurable: true,
    });
    await audioInput.trigger("change");
    await wrapper.find(".send").trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="task-queue"]').text()).toContain("queued");

    await vi.advanceTimersByTimeAsync(3000);
    await flushPromises();
    expect(wrapper.find('[data-testid="task-queue"]').text()).toContain("50%");

    await vi.advanceTimersByTimeAsync(3000);
    await flushPromises();
    expect(wrapper.find('[data-testid="review-toast"]').text()).toContain("复盘已完成");

    await wrapper.find('[data-testid="review-toast"]').trigger("click");
    await flushPromises();
    expect(wrapper.find('[data-testid="review-room"]').text()).toContain("Spring Boot");
    expect(wrapper.find('[data-testid="review-room"]').text()).not.toContain("interview.wavinterview.wav");
    expect(wrapper.find(".composer-wrap").exists()).toBe(false);
    expect(wrapper.find(".system-alert").text()).toContain("期待您的真实录音上传分析");
    expect(wrapper.find('[data-testid="review-room"]').text()).not.toContain("预分析");
    expect(wrapper.find('[data-testid="review-room"]').text()).not.toContain("低置信");
    expect(wrapper.find('[data-testid="review-room"]').text()).not.toContain("语音识别");
    expect(wrapper.find('[data-testid="review-room"]').text()).not.toContain("音频切分");
    expect(wrapper.find('[data-testid="rag-diagnosis"]').text()).toContain("条件装配");

    await wrapper.find('[data-testid="teacher-correction"] input[type="number"]').setValue(88);
    await wrapper.find('[data-testid="teacher-correction"] .send').trigger("click");
    await flushPromises();
    expect(fetch.mock.calls.find(([url]) => url.endsWith("/reviews/review-1/segments/seg-1"))).toBeTruthy();

    await wrapper.find('textarea[placeholder="给当前句子添加批注"]').setValue("补充条件装配。");
    await wrapper.findAll(".diagnosis-card .send").at(1).trigger("click");
    await flushPromises();
    expect(wrapper.find(".annotation-card").text()).toContain("补充条件装配");

    await wrapper.find(".review-exit").trigger("click");
    await flushPromises();
    expect(wrapper.find(".composer-wrap").exists()).toBe(true);
  });

  it("logs teacher out, clears review state, and stops task polling", async () => {
    const wrapper = mount(App);

    await wrapper.find(".teacher-chip").trigger("click");
    await flushPromises();
    expect(wrapper.find('[data-testid="teacher-session"]').text()).toContain("讲师 Demo");

    await vi.advanceTimersByTimeAsync(3000);
    await flushPromises();
    await vi.advanceTimersByTimeAsync(3000);
    await flushPromises();
    await wrapper.find('[data-testid="review-toast"]').trigger("click");
    await flushPromises();
    expect(wrapper.find('[data-testid="review-room"]').exists()).toBe(true);

    const taskCallsBeforeLogout = fetch.mock.calls.filter(([url]) => url.endsWith("/tasks")).length;
    await wrapper.find(".teacher-logout").trigger("click");
    await flushPromises();

    expect(fetch.mock.calls.find(([url]) => url.endsWith("/auth/logout"))).toBeTruthy();
    expect(wrapper.find(".teacher-chip").text()).toContain("讲师登录");
    expect(wrapper.find('[data-testid="teacher-session"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="review-room"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="task-queue"]').exists()).toBe(false);
    expect(wrapper.find(".status-pill").text()).toContain("讲师已退出");

    await vi.advanceTimersByTimeAsync(6000);
    await flushPromises();
    const taskCallsAfterLogout = fetch.mock.calls.filter(([url]) => url.endsWith("/tasks")).length;
    expect(taskCallsAfterLogout).toBe(taskCallsBeforeLogout);
  });
});
