<script setup lang="ts">
// Label/value detail list V2. Items with `wide` span the full row (long text).
defineProps<{ items: { label: string; value?: string | number | null; wide?: boolean; multiline?: boolean; key?: string }[]; columns?: number }>()
</script>

<template>
  <dl class="info-grid" :style="{ '--cols': columns ?? 2 }">
    <div v-for="it in items" :key="it.key ?? it.label" class="info-grid__item" :class="{ wide: it.wide }">
      <dt class="info-grid__label">{{ it.label }}</dt>
      <dd class="info-grid__val" :class="{ multiline: it.multiline }">
        <slot :name="it.key ?? it.label" :item="it">{{ it.value === null || it.value === undefined || it.value === '' ? '-' : it.value }}</slot>
      </dd>
    </div>
  </dl>
</template>

<style scoped>
.info-grid {
  display: grid;
  grid-template-columns: repeat(var(--cols), minmax(0, 1fr));
  gap: 16px 24px;
  margin: 0;
}
.info-grid__item {
  min-width: 0;
}
.info-grid__item.wide {
  grid-column: 1 / -1;
}
.info-grid__label {
  margin-bottom: 4px;
  color: var(--if-text-tertiary);
  font-size: 12px;
  font-weight: 500;
}
.info-grid__val {
  margin: 0;
  color: var(--if-text-primary);
  font-size: 13.5px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}
@media (max-width: 767px) {
  .info-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }
}
</style>
