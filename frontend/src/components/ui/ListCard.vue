<script setup lang="ts">
// Mobile list row card: the whole card is a native keyboard-accessible target.
defineProps<{ code?: string; title: string }>()
defineEmits<{ open: [] }>()
</script>

<template>
  <button type="button" class="list-card" @click="$emit('open')">
    <div class="list-card__top">
      <span v-if="code" class="mono">{{ code }}</span>
      <slot name="status" />
    </div>
    <div class="list-card__title">{{ title }}</div>
    <div v-if="$slots.default" class="list-card__meta"><slot /></div>
  </button>
</template>

<style scoped>
.list-card { display: block; width: 100%; padding: 14px 16px; background: var(--if-bg-surface); border: 1px solid var(--if-border); border-radius: var(--if-radius); color: var(--if-text-1); font: inherit; text-align: left; cursor: pointer; transition: border-color .15s, box-shadow .15s; }
.list-card:hover, .list-card:focus-visible { border-color: var(--if-brand-500); box-shadow: var(--if-shadow); }
.list-card:active { background: var(--if-bg-subtle); }
.list-card__top { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 22px; }
.list-card__title { margin: 6px 0 0; font-size: 15px; font-weight: 600; line-height: 1.45; overflow-wrap: anywhere; }
.list-card__meta { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 8px; color: var(--if-text-2); font-size: 12px; }
</style>
