<script setup lang="ts">
defineProps<{ title?: string; description?: string; padded?: boolean }>()
</script>

<template>
  <section class="section-card">
    <header v-if="title || $slots.header || $slots.actions" class="section-card__head">
      <div class="section-card__heading">
        <slot name="header"><h2 class="section-card__title">{{ title }}</h2></slot>
        <p v-if="description" class="section-card__desc">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="section-card__actions"><slot name="actions" /></div>
    </header>
    <div class="section-card__body" :class="{ 'is-flush': padded === false }"><slot /></div>
  </section>
</template>

<style scoped>
.section-card { min-width: 0; background: var(--if-bg-surface); border: 1px solid var(--if-border); border-radius: var(--if-radius); box-shadow: var(--if-shadow-sm); }
.section-card + .section-card { margin-top: var(--if-space-4); }
.section-card__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px var(--if-space-5); border-bottom: 1px solid var(--if-border); }
.section-card__heading { min-width: 0; }
.section-card__title { margin: 0; font-size: 15px; font-weight: 650; }
.section-card__desc { margin: 2px 0 0; color: var(--if-text-3); font-size: 12px; }
.section-card__actions { display: flex; flex-wrap: wrap; gap: 8px; flex-shrink: 0; }
.section-card__actions :deep(.el-button + .el-button) { margin-left: 0; }
.section-card__body { padding: var(--if-space-5); }
.section-card__body.is-flush { padding: 0; }
@media (max-width: 767px) {
  .section-card__head { padding: 12px var(--if-space-4); }
  .section-card__body { padding: var(--if-space-4); }
}
</style>
