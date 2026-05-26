<template>
  <div class="score-ring" :style="{ '--score': score, '--angle': `${score * 3.6}deg` }">
    <div class="score-ring__halo"></div>
    <div class="score-ring__core">
      <strong>{{ score }}</strong>
      <span>综合评分</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  score: {
    type: Number,
    required: true,
  },
});
</script>
