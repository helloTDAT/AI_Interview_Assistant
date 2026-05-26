import { mount, flushPromises } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App.vue";

vi.mock("echarts", () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    dispose: vi.fn(),
  })),
}));

const resumeReport = {
  quality_score: 86,
  needs_user_confirmation: false,
  analysis_engine: "llm",
  template_similarity_score: 8,
  forbidden_words: [],
  profile: {
    source_kind: "docx",
    skills: ["Python", "PyTorch", "SQL"],
    projects: ["参与智能诊断模型训练"],
    education: ["本科"],
    parse_confidence: 0.9,
    warnings: [],
  },
  dimension_scores: {
    专业技能: 88,
    项目经验: 84,
    岗位匹配: 80,
    表达量化: 72,
    教育背景: 78,
    软技能: 70,
  },
  job_fit: {
    target_position: "AI算法工程师",
    fit_score: 80,
    expected_skills: ["Python", "PyTorch", "模型评估"],
    matched_skills: ["Python", "PyTorch"],
    missing_skills: ["模型评估"],
  },
  jd_diagnosis: {
    enabled: true,
    match_rate: 80,
    core_requirements: ["Python", "PyTorch", "模型评估"],
    matched_items: ["Python", "PyTorch"],
    missing_items: ["模型评估"],
    suggestions: ["补充模型评估细节"],
  },
  interview_risks: [
    {
      risk_point: "模型评估",
      question: "请解释你如何选择模型评估指标。",
      defense_tip: "准备数据集、指标和对比实验。",
      severity: "medium",
    },
  ],
  logic_gaps: [{ issue: "技能缺少项目支撑", evidence: "项目缺少模型细节", suggestion: "补充 PyTorch 作用" }],
  reading_experience: { signal_to_noise_score: 82, cliches: [], density_notes: [], suggestions: ["保持项目符号清晰"] },
  star_optimizations: [
    {
      before: "参与模型训练",
      after: "建议改写为：使用 PyTorch 训练分类模型，并补充准确率、召回率等结果。",
      action_note: "补齐 STAR 结构",
    },
  ],
  recommendations: ["补充量化结果"],
};

const okResponse = (payload) => ({ json: vi.fn(async () => payload) });

describe("App resume report workflow", () => {
  beforeEach(() => {
    vi.stubGlobal("crypto", { randomUUID: vi.fn(() => Math.random().toString(16).slice(2)) });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url) => {
        if (url.endsWith("/chat")) return okResponse({ intent: "general_chat", message: "你好，我可以帮你分析简历。" });
        if (url.endsWith("/files/resume")) return okResponse(resumeReport);
        if (url.endsWith("/interviews/mock/start")) {
          return okResponse({ session_id: "mock-session-1", question: "请介绍一个项目。", round_index: 1, finished: false });
        }
        if (url.endsWith("/interviews/mock/message")) {
          return okResponse({
            session_id: "mock-session-1",
            question: "请补充量化结果。",
            feedback: "回答基本完整。",
            round_index: 2,
            finished: false,
          });
        }
        if (url.endsWith("/learning/questions")) return okResponse({ questions: [{ title: "请介绍你的项目贡献。" }] });
        if (url.endsWith("/interviews/audio")) return okResponse({ id: "task-1", status: "pending" });
        throw new Error(`unexpected url: ${url}`);
      }),
    );
  });

  it("does not analyze when selecting resume, then renders visual report after send", async () => {
    const wrapper = mount(App, { attachTo: document.body });
    const resumeInput = wrapper.find('input[type="file"]');
    Object.defineProperty(resumeInput.element, "files", {
      value: [new File(["demo"], "resume.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" })],
      configurable: true,
    });

    await resumeInput.trigger("change");
    expect(fetch).not.toHaveBeenCalledWith(expect.stringContaining("/files/resume"), expect.anything());
    expect(wrapper.find('[data-testid="mounted-file"]').text()).toContain("resume.docx");
    expect(wrapper.find('[data-testid="mounted-file"]').text()).toContain("DOCX");
    expect(wrapper.find(".composer-wrap #jobDescription").exists()).toBe(true);
    expect(wrapper.find(".side #jobDescription").exists()).toBe(false);
    expect(wrapper.find(".agent-list #jobDescription").exists()).toBe(false);

    await wrapper.find("#jobDescription").setValue("JD 要求 Python、PyTorch 和模型评估经验");
    await wrapper.find("textarea[placeholder]").setValue("这是我的简历，请重点优化项目经历。");
    await wrapper.find(".send").trigger("click");
    await flushPromises();

    const resumeCall = fetch.mock.calls.find(([url]) => url.endsWith("/files/resume"));
    expect(resumeCall).toBeTruthy();
    const formItems = [...resumeCall[1].body.entries()];
    expect(formItems.some(([key, value]) => key === "target_position" && value === "AI算法工程师")).toBe(true);
    expect(formItems.some(([key, value]) => key === "user_instruction" && String(value).includes("项目经历"))).toBe(true);
    expect(formItems.some(([key, value]) => key === "job_description" && String(value).includes("PyTorch"))).toBe(true);

    expect(wrapper.find('[data-testid="resume-report-card"]').exists()).toBe(true);
    expect(wrapper.find(".score-ring").exists()).toBe(true);
    expect(wrapper.findAll(".compliance-badge")).toHaveLength(3);
    expect(wrapper.find('[data-testid="ability-radar"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="jd-topology"]').exists()).toBe(true);
    expect(wrapper.find(".risk-card").text()).toContain("模型评估");
    expect(wrapper.find('[data-testid="star-diff"]').text()).toContain("STAR");

    await wrapper.find(".ghost-command").trigger("click");
    expect(wrapper.find('[data-testid="fullscreen-report"]').exists()).toBe(true);
    await wrapper.find(".close-command").trigger("click");
    expect(wrapper.find('[data-testid="fullscreen-report"]').exists()).toBe(false);
  });

  it("keeps mock interview answers on mock endpoint", async () => {
    const wrapper = mount(App);

    await wrapper.findAll(".mini-button")[0].trigger("click");
    await flushPromises();
    await wrapper.find("textarea[placeholder]").setValue("我负责后端接口和数据库设计。");
    await wrapper.find(".send").trigger("click");
    await flushPromises();

    expect(fetch.mock.calls.at(-1)[0]).toContain("/interviews/mock/message");
  });
});
