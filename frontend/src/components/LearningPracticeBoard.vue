<template>
  <section class="practice-board" data-testid="practice-board">
    <header class="practice-header">
      <div>
        <span class="eyebrow">Smart Feed</span>
        <h2>{{ targetPosition }}</h2>
        <p>根据你的简历技能、目标岗位、真实面试题和上一题表现动态推荐。</p>
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

    <section class="practice-waterfall">
      <article v-for="question in questions" :key="question.id" class="qa-card" :class="{ answered: feedbackFor(question.id) }">
        <div class="qa-card__top">
          <span class="source-badge" :class="question.source">{{ question.badge || sourceLabel(question.source) }}</span>
          <span>{{ difficultyLabel(question.difficulty) }}</span>
        </div>
        <h3>{{ question.title }}</h3>
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
import { reactive } from "vue";

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
});

defineEmits(["submit-answer", "voice-placeholder"]);

const drafts = reactive({});

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
