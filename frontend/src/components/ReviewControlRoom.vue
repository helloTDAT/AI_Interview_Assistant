<template>
  <section class="review-room" data-testid="review-room">
    <header class="review-player">
      <div>
        <span class="eyebrow">Review Control Room</span>
        <h2>{{ review.audio_filename || "面试录音复盘" }}</h2>
        <p>{{ review.summary }}</p>
      </div>
      <div class="waveform" aria-label="声纹波形">
        <button
          v-for="segment in review.segments"
          :key="segment.id"
          type="button"
          :class="waveClass(segment)"
          :style="{ height: `${28 + Math.min(58, segment.text.length * 2)}px` }"
          @click="activeSegmentId = segment.id"
        ></button>
      </div>
    </header>

    <main class="review-grid">
      <section class="transcript-panel">
        <article
          v-for="segment in review.segments"
          :key="segment.id"
          class="transcript-bubble"
          :class="[segment.speaker, { active: segment.id === activeSegmentId }]"
          @click="activeSegmentId = segment.id"
        >
          <div class="bubble-meta">
            <span>{{ segment.speaker === "interviewer" ? "面试官 Q" : "我的回答 A" }}</span>
            <strong v-if="segment.captured_question_id">真题已捕获</strong>
          </div>
          <p>{{ segment.text }}</p>
          <small>{{ formatTime(segment.start_ms) }} - {{ formatTime(segment.end_ms) }}</small>
        </article>
      </section>

      <aside class="review-insights">
        <section class="score-stack">
          <article v-for="(score, name) in review.dimension_scores" :key="name" class="score-mini">
            <strong>{{ score }}</strong>
            <span>{{ name }}</span>
          </article>
        </section>

        <section class="diagnosis-card" data-testid="rag-diagnosis">
          <div class="module-heading">
            <span>RAG 诊断</span>
            <strong>{{ activeDiagnosis?.missing_points?.length || 0 }} 个漏点</strong>
          </div>
          <h3>{{ activeDiagnosis?.question || "选择一条面试官问题查看诊断" }}</h3>
          <div class="point-list hit">
            <span v-for="point in activeDiagnosis?.hit_points || []" :key="point">{{ point }}</span>
          </div>
          <div class="point-list missing">
            <span v-for="point in activeDiagnosis?.missing_points || []" :key="point">{{ point }}</span>
          </div>
          <p>{{ activeDiagnosis?.correction_advice || "右侧会跟随左侧转写切换。" }}</p>
        </section>

        <section class="diagnosis-card">
          <div class="module-heading">
            <span>讲师批注</span>
          </div>
          <article v-for="annotation in activeAnnotations" :key="annotation.id" class="annotation-card">
            <strong>{{ annotation.author_name }}</strong>
            <p>{{ annotation.body }}</p>
          </article>
          <textarea v-model="annotationDraft" placeholder="给当前句子添加批注"></textarea>
          <button type="button" class="send small" @click="submitAnnotation">提交批注</button>
        </section>

        <section class="diagnosis-card">
          <div class="module-heading">
            <span>软技能曲线</span>
          </div>
          <div class="soft-points">
            <span v-for="point in review.acoustic_points" :key="point.time_ms" :class="point.emotion">
              {{ Math.round(point.speech_rate) }} 字/分
            </span>
          </div>
        </section>
      </aside>
    </main>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({
  review: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["annotate"]);

const activeSegmentId = ref(props.review.segments?.[0]?.id || "");
const annotationDraft = ref("");

watch(
  () => props.review.id,
  () => {
    activeSegmentId.value = props.review.segments?.[0]?.id || "";
  },
);

const activeDiagnosis = computed(() => props.review.rag_diagnostics?.find((item) => item.segment_id === activeSegmentId.value));
const activeAnnotations = computed(() => props.review.annotations?.filter((item) => item.segment_id === activeSegmentId.value) || []);

const formatTime = (ms) => {
  const total = Math.round((ms || 0) / 1000);
  const minutes = String(Math.floor(total / 60)).padStart(2, "0");
  const seconds = String(total % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
};

const waveClass = (segment) => {
  if (segment.speaker === "interviewer") return "wave-bar question";
  if ((segment.ai_score || 0) >= 80) return "wave-bar good";
  if ((segment.confidence || 1) < 0.75) return "wave-bar weak";
  return "wave-bar answer";
};

const submitAnnotation = () => {
  const body = annotationDraft.value.trim();
  if (!body || !activeSegmentId.value) return;
  emit("annotate", { segment_id: activeSegmentId.value, body });
  annotationDraft.value = "";
};
</script>
