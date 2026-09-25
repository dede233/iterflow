<script setup lang="ts">
// Label/value detail list. Items with `wide` span the full row (long text).
defineProps<{ items: { label: string; value?: string | number | null; wide?: boolean; multiline?: boolean; key?: string }[]; columns?: number }>()
</script>

<template>
  <dl class="info-grid" :style="{ '--cols': columns ?? 2 }">
    <div v-for="it in items" :key="it.key ?? it.label" class="info-grid__item" :class="{ wide: it.wide }">
      <dt>{{ it.label }}</dt>
      <dd :class="{ multiline: it.multiline }">
        <slot :name="it.key ?? it.label" :item="it">{{ it.value === null || it.value === undefined || it.value === '' ? '-' : it.value }}</slot>
      </dd>
    </div>
  </dl>
</template>

<style scoped>
.info-grid { display: grid; grid-template-columns: repeat(var(--cols), minmax(0, 1fr)); gap: 18px 24px; margin: 0; }
.info-grid__item { min-width: 0; }
.info-grid__item.wide { grid-column: 1 / -1; }
dt { margin-bottom: 4px; color: var(--if-text-3); font-size: 12px; font-weight: 500; }
dd { margin: 0; color: var(--if-text-1); font-size: 14px; line-height: 1.6; overflow-wrap: anywhere; }
@media (max-width: 767px) { .info-grid { grid-template-columns: 1fr; gap: 14px; } }
</style>
