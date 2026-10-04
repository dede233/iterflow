<script setup lang="ts">
defineProps<{ title: string; description?: string; eyebrow?: string }>()
</script>

<template>
  <header class="page-header">
    <div class="page-header__text">
      <div v-if="eyebrow || $slots.eyebrow" class="page-header__eyebrow"><slot name="eyebrow">{{ eyebrow }}</slot></div>
      <div class="page-header__title-row">
        <h1 class="page-title">{{ title }}</h1>
        <slot name="status" />
      </div>
      <p v-if="description" class="page-header__desc">{{ description }}</p>
      <slot name="meta" />
    </div>
    <div v-if="$slots.actions" class="page-header__actions"><slot name="actions" /></div>
  </header>
</template>

<style scoped>
.page-header { display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between; gap: var(--if-space-4); margin-bottom: var(--if-space-5); }
.page-header__text { flex: 1 1 20rem; min-width: 0; max-width: 100%; }
.page-header__eyebrow { margin-bottom: 4px; color: var(--if-text-3); font-family: var(--if-font-mono); font-size: 12px; overflow-wrap: anywhere; }
.page-header__title-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
.page-header__desc { margin: 6px 0 0; color: var(--if-text-2); font-size: 14px; overflow-wrap: anywhere; }
.page-header__actions { display: flex; flex: 0 1 auto; flex-wrap: wrap; min-width: 0; max-width: 100%; justify-content: flex-end; gap: 8px; }
.page-header__actions :deep(.el-button + .el-button) { margin-left: 0; }
@media (max-width: 1199px) {
  .page-header { flex-direction: column; }
  .page-header__text { flex: 0 1 auto; width: 100%; }
  .page-header__actions { justify-content: flex-start; width: 100%; }
}
@media (max-width: 767px) {
  .page-header { gap: var(--if-space-3); margin-bottom: var(--if-space-4); }
  .page-header__desc { font-size: 13px; }
}
</style>
