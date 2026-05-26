<template>
  <section class="star-section">
    <div class="module-heading">
      <span>STAR 修改胶囊</span>
      <strong>Actionable Optimization</strong>
    </div>
    <div v-if="items.length" class="star-grid" data-testid="star-diff">
      <article v-for="(item, index) in items" :key="`${item.before}-${index}`" class="star-capsule">
        <div class="star-column before">
          <small>你的原话 Before</small>
          <p>{{ item.before || "暂无可解析原文" }}</p>
        </div>
        <div class="star-column after">
          <small>AI 优化建议 After - STAR</small>
          <p>{{ item.after || "建议补充背景、任务、行动和结果。" }}</p>
        </div>
        <div class="star-column action">
          <small>优化动作说明</small>
          <p>{{ item.action_note || "补齐量化结果和个人贡献。" }}</p>
        </div>
      </article>
    </div>
    <div v-else class="star-empty">
      <strong>项目经历证据不足</strong>
      <p>上传可解析的项目经历后，会在这里生成 Before / After / 动作说明的 STAR 改写。</p>
    </div>
  </section>
</template>

<script setup>
defineProps({
  items: {
    type: Array,
    default: () => [],
  },
});
</script>
