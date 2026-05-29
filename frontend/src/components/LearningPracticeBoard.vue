<template>
  <section class="practice-board" data-testid="practice-board">
    <header class="practice-header">
      <div>
        <span class="eyebrow">Smart Feed</span>
        <h2>{{ targetPosition }}</h2>
        <p>{{ feedMessage }}</p>
        <p v-if="ragStatus" class="rag-hit-line">
          本地 RAG 已命中 {{ ragStatus.retrieved || 0 }} 条知识片段
          <span v-if="ragStatus.sources?.length"> · {{ ragStatus.sources.map((source) => source.repo || source.title).filter(Boolean).slice(0, 2).join(" / ") }}</span>
        </p>
      </div>
      <div class="practice-stats">
        <strong>{{ questions.length }}</strong>
        <span>张练习卡</span>
      </div>
    </header>

    <section class="insight-strip" aria-label="能力点亮图谱">
      <article v-for="node in insights" :key="node.skill" class="skill-node" :class="node.status">
        <span>{{ node.skill }}</span>
        <strong>{{ node.mastery }}%</strong>
      </article>
    </section>

    <section v-if="loading" class="practice-waterfall">
      <article v-for="index in 3" :key="index" class="qa-card qa-card--skeleton">
        <div class="skeleton-line short"></div>
        <div class="skeleton-line title"></div>
        <div class="skeleton-line"></div>
        <div class="skeleton-line"></div>
      </article>
    </section>

    <section v-else-if="error" class="practice-empty">
      <h3>练习推荐没有生成成功</h3>
      <p>{{ error }}</p>
      <button type="button" class="send small" @click="$emit('retry')">重新推荐</button>
    </section>

    <section v-else-if="!questions.length" class="practice-empty">
      <h3>暂时没有匹配到练习卡</h3>
      <p>可以换一个目标岗位，或先上传简历/真实面试录音沉淀更多题目。</p>
      <button type="button" class="send small" @click="$emit('retry')">重新推荐</button>
    </section>

    <section v-else class="practice-waterfall">
      <article v-for="question in questions" :key="question.id" class="qa-card" :class="{ answered: feedbackFor(question.id) }">
        <div class="qa-card__top">
          <span class="source-badge" :class="question.source">{{ question.badge || sourceLabel(question.source) }}</span>
          <span>{{ difficultyLabel(question.difficulty) }}</span>
        </div>
        <h3>{{ question.title }}</h3>
        <div v-if="question.prompt" class="question-prompt" :class="{ expanded: expandedPrompts[question.id] }">
          <p>{{ question.prompt }}</p>
          <button v-if="question.prompt.length > 72" type="button" @click="expandedPrompts[question.id] = !expandedPrompts[question.id]">
            {{ expandedPrompts[question.id] ? "收起" : "展开" }}
          </button>
        </div>
        <div class="tag-row">
          <span v-for="tag in question.skill_tags" :key="tag">{{ tag }}</span>
        </div>

        <template v-if="feedbackFor(question.id)">
          <div class="feedback-panel" data-testid="answer-feedback">
            <div class="score-chip">{{ feedbackFor(question.id).score }} 分</div>
            <p><strong>亮点：</strong>{{ feedbackFor(question.id).highlights.join("；") || "已完成作答。" }}</p>
            <p><strong>改进：</strong>{{ feedbackFor(question.id).improvements.join("；") }}</p>
            <p><strong>资深工程师思路：</strong>{{ feedbackFor(question.id).senior_answer }}</p>
          </div>
        </template>
        <template v-else>
          <textarea
            v-model="drafts[question.id]"
            :aria-label="`${question.title} 的回答`"
            placeholder="写下你的回答，尽量覆盖场景、方案、难点、结果。"
          ></textarea>
          <div class="qa-actions">
            <button type="button" class="voice-button" @click="$emit('voice-placeholder')">按住说话</button>
            <button type="button" class="send small" @click="$emit('submit-answer', question, drafts[question.id] || '')">
              提交
            </button>
          </div>
        </template>
      </article>
    </section>
  </section>
</template>

<script setup>
import { computed, reactive } from "vue";

const props = defineProps({
  questions: {
    type: Array,
    default: () => [],
  },
  insights: {
    type: Array,
    default: () => [],
  },
  feedbackById: {
    type: Object,
    default: () => ({}),
  },
  targetPosition: {
    type: String,
    required: true,
  },
  feedSource: {
    type: String,
    default: "target",
  },
  ragStatus: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: "",
  },
});

defineEmits(["submit-answer", "voice-placeholder", "retry"]);

const drafts = reactive({});
const expandedPrompts = reactive({});

const feedMessage = computed(() =>
  props.feedSource === "mounted_resume"
    ? "已基于当前简历技能、目标岗位、真实面试题和上一题表现动态推荐。"
    : props.feedSource === "active_resume"
      ? "已基于上次简历画像、目标岗位、真实面试题和上一题表现动态推荐。"
    : "基于目标岗位画像、真实面试题和上一题表现动态推荐。",
);

const feedbackFor = (id) => props.feedbackById[id];

const sourceLabel = (source) => {
  if (source === "real_interview") return "高频实战";
  if (source === "open_source") return "开源题库";
  if (source === "handbook") return "宝典题";
  return "AI 生成";
};

const difficultyLabel = (difficulty) => {
  if (difficulty === "hard") return "进阶追问";
  if (difficulty === "easy") return "巩固";
  return "标准";
};
</script>
