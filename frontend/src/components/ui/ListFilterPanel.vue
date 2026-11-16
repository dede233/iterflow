<script setup lang="ts">
import { ref, watch } from 'vue'
const props = defineProps<{ mobile: boolean; title: string; advancedCount?: number }>()
const advanced = ref(false)
watch(() => props.advancedCount, count => { if (count) advanced.value = true }, { immediate: true })
const open = defineModel<boolean>({ default: false })
defineEmits<{ search: []; reset: [] }>()
</script>

<template>
  <el-form v-if="!mobile" class="list-filters filter-panel" label-position="left" @submit.prevent>
    <div class="filter-content">
      <div class="filter-fields"><slot /></div>
      <div class="filter-actions">
        <el-button v-if="$slots.advanced" :aria-expanded="advanced" @click="advanced = !advanced">{{ advanced ? '收起筛选' : '更多筛选' }}{{ advancedCount ? ` (${advancedCount})` : '' }}</el-button>
        <el-button @click="$emit('search')">查询</el-button>
        <el-button @click="$emit('reset')">重置</el-button>
      </div>
    </div>
    <div v-if="$slots.advanced" v-show="advanced" class="advanced-filters"><slot name="advanced" /></div>
  </el-form>
  <el-drawer v-else v-model="open" :title="title" direction="rtl" size="min(420px, 100%)" destroy-on-close>
    <el-form class="mobile-list-filters" label-position="top" @submit.prevent><slot /><slot name="advanced" /></el-form>
    <template #footer><el-button @click="$emit('reset')">重置</el-button><el-button type="primary" @click="$emit('search')">查询</el-button></template>
  </el-drawer>
</template>

<style scoped>
.list-filters { container-type: inline-size; padding-bottom: var(--if-space-4); }
.filter-content { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--if-space-4); align-items: end; }
.filter-fields, .advanced-filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr)); gap: var(--if-space-4); align-items: start; }
.filter-fields:has(.el-date-editor), .advanced-filters:has(.el-date-editor) { grid-template-columns: repeat(auto-fit, minmax(min(100%, 380px), 1fr)); }
.filter-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--if-space-2); }
.filter-actions :deep(.el-button + .el-button) { margin-left: 0; }
.advanced-filters { border-top: 1px solid var(--if-border); margin-top: var(--if-space-4); padding-top: var(--if-space-4); }
.list-filters :deep(.el-form-item) { min-width: 0; max-width: 100%; margin: 0; }
.list-filters :deep(.el-form-item__label) { flex: 0 0 72px; width: 72px; height: 32px; align-items: center; line-height: 20px; margin-bottom: 0; padding: 0 var(--if-space-2) 0 0; }
.list-filters :deep(.el-form-item:has(.el-date-editor) .el-form-item__label) { flex-basis: 100px; width: 100px; }
.list-filters :deep(.el-form-item__content), .mobile-list-filters :deep(.el-form-item__content) { min-width: 0; }
.list-filters :deep(.el-input), .list-filters :deep(.el-select), .list-filters :deep(.el-input-number), .list-filters :deep(.el-date-editor) { width: 100%; max-width: 100%; }
.list-filters :deep(.el-range-input) { min-width: 0; }
.mobile-list-filters :deep(.el-input), .mobile-list-filters :deep(.el-select), .mobile-list-filters :deep(.el-input-number), .mobile-list-filters :deep(.el-date-editor) { width: 100%; max-width: 100%; }
.mobile-list-filters :deep(.el-range-input) { min-width: 0; }
@container (max-width: 900px) {
  .filter-content { grid-template-columns: minmax(0, 1fr); }
}
</style>
