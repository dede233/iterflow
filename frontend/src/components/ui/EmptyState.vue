<script setup lang="ts">
import AppIcon from './AppIcon.vue'
defineProps<{ description: string; icon?: string; compact?: boolean }>()
</script>

<template>
  <div class="empty-state" :class="{ compact }" role="status">
    <div class="empty-state__icon-wrap">
      <AppIcon :name="icon ?? 'inbox'" :size="compact ? 20 : 28" />
    </div>
    <p class="empty-state__text">{{ description }}</p>
    <div v-if="$slots.default" class="empty-state__action"><slot /></div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px 24px;
  color: var(--if-text-tertiary);
  text-align: center;
}
.empty-state.compact {
  padding: 24px 16px;
  gap: 8px;
}
.empty-state__icon-wrap {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  border-radius: var(--if-radius-lg);
  background-color: var(--if-slate-100);
  color: var(--if-slate-400);
}
.compact .empty-state__icon-wrap {
  width: 40px;
  height: 40px;
  border-radius: var(--if-radius);
}
.empty-state__text {
  margin: 0;
  font-size: 13px;
  color: var(--if-text-secondary);
  max-width: 320px;
  line-height: 1.5;
}
.empty-state__action {
  margin-top: 4px;
}
</style>
