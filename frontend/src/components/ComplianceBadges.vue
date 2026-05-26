<template>
  <div class="compliance-grid">
    <div class="compliance-badge" :class="templateState.level">
      <span class="pulse"></span>
      <div>
        <small>模板查重检测</small>
        <strong>{{ templateState.label }}</strong>
      </div>
    </div>
    <div class="compliance-badge" :class="forbiddenState.level">
      <span class="pulse"></span>
      <div>
        <small>违禁词检测</small>
        <strong>{{ forbiddenState.label }}</strong>
      </div>
    </div>
    <div class="compliance-badge" :class="confidenceState.level">
      <span class="pulse"></span>
      <div>
        <small>解析置信度</small>
        <strong>{{ confidenceState.label }}</strong>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  templateSimilarityScore: { type: Number, default: 0 },
  forbiddenWords: { type: Array, default: () => [] },
  needsUserConfirmation: { type: Boolean, default: false },
  parseConfidence: { type: Number, default: 0 },
});

const templateState = computed(() => {
  if (props.templateSimilarityScore >= 60) return { label: "模板痕迹偏重", level: "warn" };
  if (props.templateSimilarityScore >= 30) return { label: "轻微模板化", level: "notice" };
  return { label: "原创度高", level: "safe" };
});

const forbiddenState = computed(() => {
  if (props.forbiddenWords.length) return { label: `命中 ${props.forbiddenWords.length} 项`, level: "danger" };
  return { label: "安全", level: "safe" };
});

const confidenceState = computed(() => {
  if (props.needsUserConfirmation) return { label: "预分析", level: "warn" };
  if (props.parseConfidence >= 80) return { label: "可信", level: "safe" };
  return { label: "需复核", level: "notice" };
});
</script>
