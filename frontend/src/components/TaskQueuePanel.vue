<template>
  <section class="task-queue" data-testid="task-queue">
    <div class="module-heading">
      <span>复盘任务队列</span>
      <button type="button" class="ghost-command" @click="$emit('refresh')">刷新</button>
    </div>
    <article
      v-for="task in tasks"
      :key="task.id"
      class="task-row"
      :class="{ completed: task.status === 'completed', running: task.status === 'running' }"
      @click="$emit('open-review', task)"
    >
      <div>
        <strong>{{ task.stage || task.status }}</strong>
        <p>{{ task.message }}</p>
      </div>
      <span>{{ task.progress || 0 }}%</span>
    </article>
  </section>
</template>

<script setup>
defineProps({
  tasks: {
    type: Array,
    default: () => [],
  },
});

defineEmits(["refresh", "open-review"]);
</script>
