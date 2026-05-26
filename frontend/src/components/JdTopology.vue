<template>
  <div class="chart-block">
    <div class="module-heading">
      <span>JD 匹配拓扑</span>
      <strong>{{ report.jdDiagnosis.enabled ? `${report.jdDiagnosis.match_rate}% Match` : "岗位画像模式" }}</strong>
    </div>
    <div v-if="report.jdDiagnosis.enabled" ref="chartRef" class="echart topology-chart" data-testid="jd-topology"></div>
    <div v-else class="topology-empty">
      <strong>当前基于目标岗位画像评估</strong>
      <p>粘贴具体公司的 JD 后，这里会展示简历技能与 JD 要求之间的命中连线和缺失节点。</p>
      <div class="skill-cloud">
        <span v-for="skill in fallbackSkills" :key="skill">{{ skill }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";

const props = defineProps({
  report: {
    type: Object,
    required: true,
  },
});

const chartRef = ref(null);
let chart;

const fallbackSkills = computed(() => [
  ...new Set([...(props.report.jobFit.matched_skills || []), ...(props.report.jobFit.missing_skills || [])]),
].slice(0, 10));

const render = () => {
  if (!chartRef.value || !props.report.jdDiagnosis.enabled) return;
  chart ||= echarts.init(chartRef.value);
  const resumeSkills = (props.report.profile.skills || props.report.jobFit.matched_skills || []).slice(0, 8);
  const jdSkills = props.report.jdDiagnosis.core_requirements.slice(0, 10);
  const matched = new Set(props.report.jdDiagnosis.matched_items);
  const missing = new Set(props.report.jdDiagnosis.missing_items);
  const nodes = [
    ...resumeSkills.map((skill, index) => ({
      name: `简历:${skill}`,
      label: { formatter: skill },
      x: 90,
      y: 48 + index * 42,
      symbolSize: 34,
      itemStyle: { color: "#2563eb" },
    })),
    ...jdSkills.map((skill, index) => ({
      name: `JD:${skill}`,
      label: { formatter: skill },
      x: 390,
      y: 42 + index * 38,
      symbolSize: missing.has(skill) ? 38 : 32,
      itemStyle: { color: missing.has(skill) ? "#ef4444" : "#14b8a6" },
    })),
  ];
  const links = jdSkills
    .filter((skill) => matched.has(skill))
    .flatMap((skill) =>
      resumeSkills
        .filter((resumeSkill) => resumeSkill.toLowerCase() === skill.toLowerCase())
        .map((resumeSkill) => ({
          source: `简历:${resumeSkill}`,
          target: `JD:${skill}`,
          lineStyle: { width: 4, color: "rgba(20, 184, 166, 0.72)", curveness: 0.12 },
        })),
    );

  chart.setOption({
    animationDuration: 900,
    series: [
      {
        type: "graph",
        layout: "none",
        roam: false,
        data: nodes,
        links,
        edgeSymbol: ["none", "arrow"],
        label: { show: true, color: "#0f172a", fontSize: 12 },
        lineStyle: { opacity: 0.9 },
      },
    ],
  });
};

onMounted(() => {
  render();
  window.addEventListener("resize", render);
});
watch(() => props.report, render, { deep: true });
onBeforeUnmount(() => {
  window.removeEventListener("resize", render);
  chart?.dispose();
});
</script>
