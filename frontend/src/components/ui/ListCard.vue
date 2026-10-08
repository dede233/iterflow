<script setup lang="ts">
// Mobile list row card V2: the whole card is a native keyboard-accessible target.
defineProps<{ code?: string; title: string }>()
defineEmits<{ open: [] }>()
</script>

<template>
  <button type="button" class="list-card" @click="$emit('open')">
    <div class="list-card__top">
      <span v-if="code" class="mono list-card__code">{{ code }}</span>
      <slot name="status" />
    </div>
    <div class="list-card__title">{{ title }}</div>
    <div v-if="$slots.default" class="list-card__meta"><slot /></div>
  </button>
</template>

<style scoped>
.list-card {
  display: block;
  width: 100%;
  padding: 14px 16px;
  background-color: var(--if-bg-surface);
  border: 1px solid var(--if-border);
  border-radius: var(--if-radius);
  color: var(--if-text-primary);
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: all 0.15s ease;
  box-shadow: var(--if-shadow-xs);
}
.list-card:hover,
.list-card:focus-visible {
  border-color: var(--if-brand-400);
  box-shadow: var(--if-shadow-sm);
}
.list-card:active {
  background-color: var(--if-slate-50);
}
.list-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 22px;
}
.list-card__code {
  font-family: var(--if-font-mono);
  font-size: 11.5px;
  color: var(--if-text-tertiary);
  font-weight: 500;
}
.list-card__title {
  margin: 6px 0 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.45;
  color: var(--if-text-primary);
  overflow-wrap: anywhere;
}
.list-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: 8px;
  color: var(--if-text-secondary);
  font-size: 12px;
}
</style>
