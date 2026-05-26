<template>
  <section class="insight-stack">
    <div class="module-heading">
      <span>动态预警</span>
      <strong>Alert & Insights</strong>
    </div>

    <article v-for="risk in risks" :key="risk.question || risk.risk_point" class="risk-card">
      <div class="risk-card__top">
        <span class="risk-dot"></span>
        <strong>{{ risk.risk_point || "高频追问点" }}</strong>
        <em>{{ risk.severity || "medium" }}</em>
      </div>
      <p>{{ risk.question || "请准备说明该经历的真实背景、个人贡献和量化结果。" }}</p>
      <small>{{ risk.defense_tip || risk.why_it_matters || "建议提前准备可验证证据。" }}</small>
    </article>

    <article v-for="gap in gaps" :key="gap.issue" class="gap-card">
      <strong>{{ gap.issue || "逻辑断层" }}</strong>
      <p>{{ gap.evidence || "技能声明和项目证据之间存在支撑不足。" }}</p>
      <small>{{ gap.suggestion || "补充项目中的具体方法、工具和结果。" }}</small>
    </article>

    <article class="reading-card">
      <div>
        <small>阅读信噪比</small>
        <strong>{{ reading.signal_to_noise_score }}</strong>
      </div>
      <p>{{ readingSummary }}</p>
    </article>
  </section>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  report: {
    type: Object,
    required: true,
  },
});

const risks = computed(() =>
  props.report.interviewRisks.length
    ? props.report.interviewRisks.slice(0, 4)
    : [
        {
          risk_point: "项目细节",
          question: "请选择一个最有代表性的项目，说明你的具体贡献和量化结果。",
          defense_tip: "用 STAR 法则准备 1 分钟项目说明。",
          severity: "low",
        },
      ],
);

const gaps = computed(() => props.report.logicGaps.slice(0, 3));
const reading = computed(() => props.report.readingExperience);
const readingSummary = computed(() => {
  const notes = [...reading.value.density_notes, ...reading.value.suggestions].filter(Boolean);
  if (notes.length) return notes[0];
  if (reading.value.cliches.length) return `发现 ${reading.value.cliches.length} 个套话表达，建议替换为行动证据。`;
  return "当前阅读动线较清晰，继续优先展示岗位相关项目证据。";
});
</script>
