<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getDashboardOverview } from '@/api/dashboard'
import DashboardOverviewContent from '@/components/DashboardOverviewContent.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import type { DashboardOverview } from '@/types/dashboard'

const loading = ref(true)
const overview = ref<DashboardOverview | null>(null)
const failed = ref(false)

async function loadOverview(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    overview.value = await getDashboardOverview()
  } catch {
    failed.value = true
    ElMessage.error('系统概览加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

onMounted(() => { void loadOverview() })
</script>

<template>
  <div class="page">
    <el-skeleton v-if="loading" :rows="8" animated aria-label="正在加载系统概览" />
    <template v-else-if="failed">
      <PageHeader title="首页 / 系统概览" description="当前可访问范围内的反馈、需求、版本与发布情况。" eyebrow="工作台" />
      <ErrorState title="系统概览加载失败" description="请检查网络后重试。" retry-label="重新加载" @retry="loadOverview" />
    </template>
    <DashboardOverviewContent v-else-if="overview" :overview="overview" />
  </div>
</template>
