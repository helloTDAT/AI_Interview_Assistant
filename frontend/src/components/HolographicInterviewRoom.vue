<template>
  <section class="interview-room" data-testid="interview-room">
    <div class="interviewer-stage">
      <header class="interview-room__header">
        <div>
          <span class="eyebrow">Holographic Interview Room</span>
          <h2>{{ modeLabel }}</h2>
          <p>当前岗位：{{ targetPosition }} / {{ stateLabel }}</p>
        </div>
        <div class="interview-meta">
          <span>{{ phaseLabel }}</span>
          <strong>{{ roundText }}</strong>
          <small v-if="currentTurn?.difficulty_level">{{ difficultyLabel }}</small>
        </div>
        <button type="button" class="ghost-command" @click="$emit('exit')">退出面试舱</button>
      </header>

      <div class="ai-core" :class="currentTurn?.state || 'Greeting'">
        <div class="logic-map" aria-hidden="true">
          <span v-for="node in logicNodes" :key="node" :class="{ active: node === currentTurn?.state }"></span>
        </div>
        <div class="voice-orbit" aria-label="AI 面试官声纹">
          <i v-for="index in 36" :key="index" :style="{ '--h': `${28 + ((index * 17) % 62)}%`, '--d': `${index * 22}ms` }"></i>
        </div>
        <article class="current-question">
          <span>AI Interviewer / {{ questionTypeLabel }}</span>
          <h3>{{ currentTurn?.question || "正在准备第一道问题..." }}</h3>
          <p v-if="currentTurn?.question_intent">{{ currentTurn.question_intent }}</p>
          <p v-if="currentTurn?.probing_reason">{{ currentTurn.probing_reason }}</p>
        </article>
      </div>
    </div>

    <aside class="interview-dashboard">
      <section class="mode-switch">
        <button
          v-for="option in modeOptions"
          :key="option.value"
          type="button"
          :class="{ active: mode === option.value }"
          :disabled="Boolean(sessionId)"
          @click="$emit('mode-change', option.value)"
        >
          {{ option.label }}
        </button>
      </section>

      <section class="phase-panel">
        <div class="module-heading">
          <span>当前阶段</span>
          <strong>{{ roundText }}</strong>
        </div>
        <p>{{ phaseLabel }}</p>
        <small v-if="currentTurn?.anchor_project">锚定经历：{{ anchorSummary }}</small>
        <small v-else>未读取到简历项目，本轮按岗位通用流程推进。</small>
      </section>

      <section class="pressure-panel">
        <div class="module-heading">
          <span>压力仪表盘</span>
          <strong>{{ currentTurn?.pressure_level || 0 }}%</strong>
        </div>
        <div class="pressure-track">
          <span :style="{ width: `${currentTurn?.pressure_level || 0}%` }"></span>
        </div>
        <div class="score-grid">
          <article>
            <strong>{{ currentTurn?.answer_depth_score || 0 }}</strong>
            <span>回答深度</span>
          </article>
          <article v-for="(score, name) in skillScores" :key="name">
            <strong>{{ score }}</strong>
            <span>{{ name }}</span>
          </article>
        </div>
      </section>

      <section class="live-log">
        <div class="module-heading">
          <span>实时对话日志</span>
          <strong>{{ transcript.length }}</strong>
        </div>
        <article v-for="item in transcript" :key="item.id" :class="item.role">
          <span>{{ item.role === "assistant" ? "AI" : "ME" }}</span>
          <p>{{ item.text }}</p>
        </article>
      </section>

      <section class="keyword-panel">
        <div class="module-heading">
          <span>本题关键点</span>
        </div>
        <div class="tag-row interview-tags">
          <span v-for="keyword in currentTurn?.detected_keywords || []" :key="keyword">{{ keyword }}</span>
          <span v-if="!(currentTurn?.detected_keywords || []).length">等待回答</span>
        </div>
      </section>
    </aside>

    <footer class="interview-deck">
      <button
        type="button"
        class="mic-button"
        :class="{ pressed: micPressed }"
        @mousedown="$emit('mic-placeholder', true)"
        @mouseup="$emit('mic-placeholder', false)"
        @mouseleave="$emit('mic-placeholder', false)"
      >
        <span></span>
      </button>
      <textarea
        :value="draft"
        :placeholder="inputPlaceholder"
        :disabled="isFinished"
        @input="$emit('draft-change', $event.target.value)"
        @keydown.enter.exact.prevent="$emit('send')"
      ></textarea>
      <button type="button" class="send" :disabled="isFinished" @click="$emit('send')">{{ sendLabel }}</button>
      <button type="button" class="danger-command" :disabled="isFinished" @click="$emit('finish')">
        {{ isFinished ? "已结束" : "结束面试" }}
      </button>
    </footer>

    <section v-if="currentTurn?.final_report" class="interview-final" data-testid="interview-final">
      <h3>最终能力图谱</h3>
      <p>{{ currentTurn.final_report.summary }}</p>
      <div class="score-grid">
        <article v-for="(score, name) in currentTurn.final_report.dimension_scores" :key="name">
          <strong>{{ score }}</strong>
          <span>{{ name }}</span>
        </article>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  sessionId: { type: String, default: "" },
  targetPosition: { type: String, required: true },
  mode: { type: String, required: true },
  transcript: { type: Array, default: () => [] },
  currentTurn: { type: Object, default: null },
  draft: { type: String, default: "" },
  micPressed: { type: Boolean, default: false },
});

defineEmits(["mode-change", "draft-change", "send", "finish", "exit", "mic-placeholder"]);

const modeOptions = [
  { value: "project_deep_dive", label: "综合模拟" },
  { value: "tech_blitz", label: "技术快问" },
  { value: "behavioral", label: "行为抗压" },
];

const typeLabels = {
  project_warmup: "项目暖场",
  project_basic: "项目基础",
  project_tech_basic: "项目技术基础",
  project_implementation: "项目实现",
  project_deep: "项目深挖",
  project: "简历项目",
  role_core: "岗位基础",
  foundation: "计算机基础",
  algorithm: "算法思维",
  system_design: "系统设计",
  open: "开放问题",
  behavioral: "行为沟通",
  technical: "技术考察",
  reverse_qa: "反向提问",
  summary: "总结复盘",
};

const difficultyLabels = {
  easy: "基础",
  medium: "中等",
  hard: "深入",
};

const logicNodes = ["Greeting", "ListeningParsing", "DecisionMaking", "Probing", "NewQuestion", "ReverseQA", "Closing"];

const modeLabel = computed(() => modeOptions.find((item) => item.value === props.mode)?.label || "综合模拟");
const stateLabel = computed(() => props.currentTurn?.state || "Greeting");
const questionTypeLabel = computed(() => typeLabels[props.currentTurn?.question_type] || "综合考察");
const phaseLabel = computed(() => props.currentTurn?.phase_label || questionTypeLabel.value);
const skillScores = computed(() => props.currentTurn?.skill_scores || {});
const roundText = computed(() => `第 ${props.currentTurn?.round_index || 1}/${props.currentTurn?.round_total || 8} 题`);
const difficultyLabel = computed(() => difficultyLabels[props.currentTurn?.difficulty_level] || props.currentTurn?.difficulty_level);
const anchorSummary = computed(() => {
  const text = props.currentTurn?.anchor_project || "";
  const firstLine = text.split(/\n/).find(Boolean) || text;
  return firstLine.length > 46 ? `${firstLine.slice(0, 46)}...` : firstLine;
});
const inputPlaceholder = computed(() =>
  isFinished.value ? "本轮面试已结束，可查看最终能力图谱。" : props.currentTurn?.reverse_question_prompt || "输入你的回答。麦克风按钮为 UI 占位，当前不会进行真实语音识别。",
);
const isFinished = computed(() => Boolean(props.currentTurn?.finished));
const sendLabel = computed(() => (props.currentTurn?.state === "ReverseQA" ? "提交反问" : "发送回答"));
</script>
