<template>
  <section class="review-room" data-testid="review-room">
    <header class="review-player review-player--compact">
      <div class="review-title-block">
        <div class="review-title-row">
          <span class="eyebrow">Review Control Room</span>
          <button type="button" class="ghost-command review-exit" @click="emit('exit')">返回工作台</button>
        </div>
        <h2>面试录音复盘</h2>
        <div class="review-file-chip" :title="review.audio_filename || '未命名录音'">
          {{ review.audio_filename || "未命名录音" }}
        </div>
        <p>{{ review.summary }}</p>
        <div class="review-stats" aria-label="复盘状态">
          <span>逐句复盘</span>
          <span>真题捕获</span>
          <span>RAG 诊断</span>
          <span>讲师复核</span>
        </div>
      </div>

      <div class="review-wave-panel">
        <div class="waveform timeline" aria-label="声纹时间轴">
          <button
            v-for="segment in review.segments"
            :key="segment.id"
            type="button"
            :class="[waveClass(segment), { active: segment.id === activeSegmentId }]"
            :style="{ height: `${waveHeight(segment)}px` }"
            :title="speakerLabel(segment)"
            @click="selectSegment(segment)"
          ></button>
        </div>
        <div class="timeline-legend">
          <span><i class="legend-system"></i>提示</span>
          <span><i class="legend-question"></i>提问</span>
          <span><i class="legend-answer"></i>回答</span>
          <span><i class="legend-captured"></i>捕获</span>
        </div>
      </div>
    </header>

    <main class="review-grid">
      <section class="transcript-panel transcript-panel--scroll">
        <article
          v-for="segment in review.segments"
          :key="segment.id"
          :class="segmentCardClass(segment)"
          @click="selectSegment(segment)"
        >
          <div class="bubble-meta">
            <span>{{ speakerLabel(segment) }}</span>
            <strong v-if="segment.captured_question_id || segment.captured_question_title">真题已捕获</strong>
          </div>
          <p>{{ segment.text }}</p>
          <small>{{ formatTime(segment.start_ms) }} - {{ formatTime(segment.end_ms) }}</small>
        </article>
      </section>

      <aside class="review-insights review-insights--scroll">
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
          <template v-if="activeDiagnosis">
            <h3>{{ activeDiagnosis.question }}</h3>
            <div class="point-list hit">
              <span v-for="point in activeDiagnosis.hit_points || []" :key="point">{{ point }}</span>
            </div>
            <div class="point-list missing">
              <span v-for="point in activeDiagnosis.missing_points || []" :key="point">{{ point }}</span>
            </div>
            <p>{{ activeDiagnosis.correction_advice }}</p>
          </template>
          <p v-else class="empty-copy">
            选择面试官问题后查看知识点诊断。
          </p>
        </section>

        <section class="diagnosis-card teacher-review-card" data-testid="teacher-correction">
          <div class="module-heading">
            <span>讲师修正</span>
            <strong v-if="activeSegment?.teacher_score">人工 {{ activeSegment.teacher_score }}</strong>
          </div>
          <template v-if="activeSegment && activeSegment.speaker !== 'system'">
            <div class="correction-grid">
              <label>
                角色
                <select v-model="segmentDraft.speaker">
                  <option value="interviewer">面试官 Q</option>
                  <option value="student">学生 A</option>
                </select>
              </label>
              <label>
                人工分
                <input v-model.number="segmentDraft.teacher_score" type="number" min="0" max="100" />
              </label>
            </div>
            <label class="capture-toggle">
              <input v-model="segmentDraft.captured" type="checkbox" />
              标记为真题捕获
            </label>
            <input
              v-if="segmentDraft.captured"
              v-model="segmentDraft.captured_question_title"
              class="captured-title-input"
              placeholder="真题标题，留空则使用当前句子"
            />
            <textarea v-model="segmentDraft.text" placeholder="修正当前句子的转写文本"></textarea>
            <button type="button" class="send small" @click="saveSegmentCorrection">保存修正</button>
          </template>
          <p v-else class="empty-copy">当前提示段用于说明流程，讲师可选择下方问答片段批注。</p>
        </section>

        <section class="diagnosis-card">
          <div class="module-heading">
            <span>讲师批注</span>
          </div>
          <article v-for="annotation in activeAnnotations" :key="annotation.id" class="annotation-card">
            <strong>{{ annotation.author_name }}</strong>
            <p>{{ annotation.body }}</p>
          </article>
          <textarea v-model="annotationDraft" :disabled="!activeSegment || activeSegment.speaker === 'system'" placeholder="给当前句子添加批注"></textarea>
          <button type="button" class="send small" :disabled="!activeSegment || activeSegment.speaker === 'system'" @click="submitAnnotation">提交批注</button>
        </section>

        <section class="diagnosis-card">
          <div class="module-heading">
            <span>软技能曲线</span>
          </div>
          <div v-if="review.acoustic_points?.length" class="soft-points">
            <span v-for="point in review.acoustic_points" :key="point.time_ms" :class="point.emotion">
              {{ Math.round(point.speech_rate) }} 字/分
            </span>
          </div>
          <p v-else class="empty-copy">暂无可用声学指标。</p>
        </section>
      </aside>
    </main>
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";

const props = defineProps({
  review: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["annotate", "update-segment", "exit"]);

const firstRealSegmentId = () => props.review.segments?.find((segment) => segment.speaker !== "system")?.id || props.review.segments?.[0]?.id || "";

const activeSegmentId = ref(firstRealSegmentId());
const annotationDraft = ref("");
const segmentDraft = reactive({
  text: "",
  speaker: "student",
  teacher_score: null,
  captured: false,
  captured_question_title: "",
});

const activeSegment = computed(() => props.review.segments?.find((segment) => segment.id === activeSegmentId.value));
const activeDiagnosis = computed(() => props.review.rag_diagnostics?.find((item) => item.segment_id === activeSegmentId.value));
const activeAnnotations = computed(() => props.review.annotations?.filter((item) => item.segment_id === activeSegmentId.value) || []);

watch(
  () => props.review.id,
  () => {
    activeSegmentId.value = firstRealSegmentId();
    resetSegmentDraft();
  },
);

watch(activeSegment, resetSegmentDraft, { immediate: true });

function resetSegmentDraft() {
  const segment = activeSegment.value;
  segmentDraft.text = segment?.text || "";
  segmentDraft.speaker = segment?.speaker === "interviewer" ? "interviewer" : "student";
  segmentDraft.teacher_score = segment?.teacher_score ?? segment?.ai_score ?? null;
  segmentDraft.captured = Boolean(segment?.captured_question_id || segment?.captured_question_title);
  segmentDraft.captured_question_title = segment?.captured_question_title || "";
}

const formatTime = (ms) => {
  const total = Math.round((ms || 0) / 1000);
  const minutes = String(Math.floor(total / 60)).padStart(2, "0");
  const seconds = String(total % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
};

const speakerLabel = (segment) => {
  if (segment.speaker === "system") return "复盘提示";
  return segment.speaker === "interviewer" ? "面试官 Q" : "我的回答 A";
};

const selectSegment = (segment) => {
  activeSegmentId.value = segment.id;
};

const waveHeight = (segment) => {
  if (segment.speaker === "system") return 18;
  return Math.max(18, Math.min(52, 18 + Math.round((segment.text?.length || 0) / 4)));
};

const waveClass = (segment) => {
  if (segment.speaker === "system") return "wave-bar system";
  if (segment.captured_question_id || segment.captured_question_title) return "wave-bar captured";
  if (segment.speaker === "interviewer") return "wave-bar question";
  if ((segment.ai_score || 0) >= 80) return "wave-bar good";
  return "wave-bar answer";
};

const segmentCardClass = (segment) => [
  segment.speaker === "system" ? "system-alert" : "transcript-bubble",
  segment.speaker,
  { active: segment.id === activeSegmentId.value },
];

const submitAnnotation = () => {
  const body = annotationDraft.value.trim();
  if (!body || !activeSegmentId.value || activeSegment.value?.speaker === "system") return;
  emit("annotate", { segment_id: activeSegmentId.value, body });
  annotationDraft.value = "";
};

const saveSegmentCorrection = () => {
  const segment = activeSegment.value;
  if (!segment || segment.speaker === "system") return;
  emit("update-segment", {
    segment_id: segment.id,
    updates: {
      text: segmentDraft.text,
      speaker: segmentDraft.speaker,
      teacher_score: segmentDraft.teacher_score,
      captured_question_title: segmentDraft.captured ? segmentDraft.captured_question_title || segmentDraft.text : "",
    },
  });
};
</script>
