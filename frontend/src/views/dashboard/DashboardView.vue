<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getDashboardOverview } from '@/api/dashboard'
import DashboardOverviewContent from '@/components/DashboardOverviewContent.vue'
import type { DashboardOverview } from '@/types/dashboard'

const loading = ref(true)
const overview = ref<DashboardOverview | null>(null)
const failed = ref(false)

onMounted(async () => {
  try {
    overview.value = await getDashboardOverview()
  } catch {
    failed.value = true
    ElMessage.error('系统概览加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page">
    <el-skeleton v-if="loading" :rows="8" animated aria-label="正在加载系统概览" />
    <el-result v-else-if="failed" icon="error" title="系统概览加载失败" sub-title="请稍后刷新重试" />
    <DashboardOverviewContent v-else-if="overview" :overview="overview" />
  </div>
</template>
