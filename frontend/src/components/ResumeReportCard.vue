<template>
  <article class="resume-report-card" data-testid="resume-report-card">
    <div v-if="report.needsUserConfirmation" class="precheck-banner">
      当前只是预分析：解析置信度较低，请确认简历文本后再用于正式投递判断。
    </div>

    <header class="report-overview">
      <div class="overview-copy">
        <span class="eyebrow">Resume Health Scanner</span>
        <h2>{{ report.targetPosition }}</h2>
        <p>已完成多维体检，优先查看得分环、风险灯和技能图谱。</p>
      </div>
      <ScoreRing :score="report.qualityScore" />
      <ComplianceBadges
        :template-similarity-score="report.templateSimilarityScore"
        :forbidden-words="report.forbiddenWords"
        :needs-user-confirmation="report.needsUserConfirmation"
        :parse-confidence="report.parseConfidence"
      />
    </header>

    <div class="report-toolbar">
      <span>分析引擎：{{ engineLabel }}</span>
      <button type="button" class="ghost-command" @click="$emit('open-fullscreen', report.source)">进入全屏报告</button>
    </div>

    <main class="report-main">
      <section class="visual-zone">
        <AbilityRadar :scores="report.dimensionScores" />
        <JdTopology :report="report" />
      </section>
      <RiskInsightPanel :report="report" />
    </main>

    <StarDiffCapsules :items="report.starOptimizations" />
  </article>
</template>

<script setup>
import { computed } from "vue";
import { normalizeResumeReport } from "@/utils/normalizeResumeReport";
import AbilityRadar from "./AbilityRadar.vue";
import ComplianceBadges from "./ComplianceBadges.vue";
import JdTopology from "./JdTopology.vue";
import RiskInsightPanel from "./RiskInsightPanel.vue";
import ScoreRing from "./ScoreRing.vue";
import StarDiffCapsules from "./StarDiffCapsules.vue";

const props = defineProps({
  rawReport: {
    type: Object,
    required: true,
  },
});

defineEmits(["open-fullscreen"]);

const report = computed(() => normalizeResumeReport(props.rawReport));
const engineLabel = computed(() => (report.value.analysisEngine === "llm" ? "LLM 智能分析" : "规则兜底分析"));
</script>
