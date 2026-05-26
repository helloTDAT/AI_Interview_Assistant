<template>
  <div class="fullscreen-report" data-testid="fullscreen-report">
    <div class="fullscreen-report__bar">
      <div>
        <span class="eyebrow">Full Report</span>
        <h2>{{ report.targetPosition }} 简历体检仪</h2>
      </div>
      <button type="button" class="close-command" @click="$emit('close')">关闭</button>
    </div>
    <ResumeReportCard :raw-report="rawReport" @open-fullscreen="() => {}" />
  </div>
</template>

<script setup>
import { computed } from "vue";
import { normalizeResumeReport } from "@/utils/normalizeResumeReport";
import ResumeReportCard from "./ResumeReportCard.vue";

const props = defineProps({
  rawReport: {
    type: Object,
    required: true,
  },
});

defineEmits(["close"]);

const report = computed(() => normalizeResumeReport(props.rawReport));
</script>
