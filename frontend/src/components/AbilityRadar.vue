<template>
  <div class="chart-block">
    <div class="module-heading">
      <span>能力多边形</span>
      <strong>Neural Radar</strong>
    </div>
    <div ref="chartRef" class="echart radar-chart" data-testid="ability-radar"></div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";

const props = defineProps({
  scores: {
    type: Object,
    required: true,
  },
});

const chartRef = ref(null);
let chart;

const render = () => {
  if (!chartRef.value) return;
  chart ||= echarts.init(chartRef.value);
  const names = Object.keys(props.scores);
  chart.setOption({
    animationDuration: 900,
    color: ["#2563eb"],
    radar: {
      radius: "66%",
      splitNumber: 4,
      indicator: names.map((name) => ({ name, max: 100 })),
      axisName: { color: "#334155", fontSize: 12 },
      axisLine: { lineStyle: { color: "rgba(37, 99, 235, 0.28)" } },
      splitLine: { lineStyle: { color: "rgba(15, 23, 42, 0.12)" } },
      splitArea: { areaStyle: { color: ["rgba(37, 99, 235, 0.02)", "rgba(20, 184, 166, 0.04)"] } },
    },
    series: [
      {
        type: "radar",
        symbol: "circle",
        symbolSize: 7,
        lineStyle: { width: 3, color: "#2563eb" },
        areaStyle: { color: "rgba(37, 99, 235, 0.18)" },
        itemStyle: { color: "#14b8a6", borderColor: "#ffffff", borderWidth: 2 },
        data: [{ value: names.map((name) => props.scores[name]), name: "能力面积" }],
      },
    ],
  });
};

onMounted(() => {
  render();
  window.addEventListener("resize", render);
});
watch(() => props.scores, render, { deep: true });
onBeforeUnmount(() => {
  window.removeEventListener("resize", render);
  chart?.dispose();
});
</script>
