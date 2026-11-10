<script setup lang="ts">
import { ref, watch } from 'vue'
const props = defineProps<{ mobile: boolean; title: string; advancedCount?: number }>()
const advanced = ref(false)
watch(() => props.advancedCount, count => { if (count) advanced.value = true }, { immediate: true })
const open = defineModel<boolean>({ default: false })
defineEmits<{ search: []; reset: [] }>()
</script>

<template>
  <el-form v-if="!mobile" class="list-filters filter-panel" inline @submit.prevent>
    <slot />
    <el-form-item v-if="$slots.advanced"><el-button :aria-expanded="advanced" @click="advanced = !advanced">{{ advanced ? '收起筛选' : '更多筛选' }}{{ advancedCount ? ` (${advancedCount})` : '' }}</el-button></el-form-item>
    <div v-if="$slots.advanced" v-show="advanced" class="advanced-filters"><slot name="advanced" /></div>
    <el-form-item><el-button type="primary" @click="$emit('search')">查询</el-button><el-button @click="$emit('reset')">重置</el-button></el-form-item>
  </el-form>
  <el-drawer v-else v-model="open" :title="title" direction="rtl" size="min(420px, 100%)" destroy-on-close>
    <el-form class="mobile-list-filters" label-position="top" @submit.prevent><slot /><slot name="advanced" /></el-form>
    <template #footer><el-button @click="$emit('reset')">重置</el-button><el-button type="primary" @click="$emit('search')">查询</el-button></template>
  </el-drawer>
</template>

<style scoped>
.advanced-filters { flex-basis: 100%; width: 100%; border-top: 1px solid var(--if-border); padding-top: 12px; }
.list-filters { display: flex; flex-wrap: wrap; align-items: center; gap: 0 16px; }
.list-filters :deep(.el-form-item) { margin-right: 0; }
.list-filters :deep(.el-form-item) { max-width: 100%; }
.list-filters :deep(.el-form-item__content), .mobile-list-filters :deep(.el-form-item__content) { min-width: 0; }
.list-filters :deep(.el-input), .list-filters :deep(.el-select), .list-filters :deep(.el-input-number) { width: 180px; max-width: 100%; }
.list-filters :deep(.el-date-editor) { width: 280px; max-width: 100%; }
.mobile-list-filters :deep(.el-input), .mobile-list-filters :deep(.el-select), .mobile-list-filters :deep(.el-input-number), .mobile-list-filters :deep(.el-date-editor) { width: 100%; max-width: 100%; }
.mobile-list-filters :deep(.el-range-input) { min-width: 0; }
</style>
