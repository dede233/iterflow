<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { getDashboardOverview } from '@/api/dashboard'
import DashboardOverviewContent from '@/components/DashboardOverviewContent.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import type { DashboardOverview } from '@/types/dashboard'
import { usePersonalRequirements } from '@/composables/usePersonalRequirements'

const auth = useAuthStore()
const loading = ref(true)
const overview = ref<DashboardOverview | null>(null)
const failed = ref(false)
let sequence = 0
let disposed = false
const identity = computed(() => `${auth.user?.id}:${auth.permissionCodes.join(',')}`)
const loadedIdentity = ref('')
const workQueue = usePersonalRequirements(() => [auth.user?.id, loadedIdentity.value === identity.value && Boolean(overview.value?.requirements) && auth.hasPermission('rd.requirement.view'), identity.value] as const)

async function loadOverview(): Promise<void> {
  if (disposed) return
  const current = ++sequence
  const requestedIdentity = identity.value
  loading.value = true
  failed.value = false
  overview.value = null
  try {
    const result = await getDashboardOverview()
    if (current === sequence) {
      loadedIdentity.value = requestedIdentity
      overview.value = result
    }
  } catch {
    if (current === sequence) {
      failed.value = true
      ElMessage.error('系统概览加载失败，请稍后重试')
    }
  } finally {
    if (current === sequence) loading.value = false
  }
}

watch(identity, () => { void loadOverview() }, { flush: 'sync' })
onMounted(() => { void loadOverview() })
onBeforeUnmount(() => { disposed = true; sequence++ })
</script>

<template>
  <div class="page">
    <el-skeleton v-if="loading" :rows="8" animated aria-label="正在加载系统概览" />
    <template v-else-if="failed">
      <PageHeader title="我的工作台" description="先处理需要你参与的事项，再查看团队进展。" eyebrow="工作台" />
      <ErrorState title="系统概览加载失败" description="请检查网络后重试。" retry-label="重新加载" @retry="loadOverview" />
    </template>
    <DashboardOverviewContent v-else-if="overview" :overview="overview" :viewer-id="auth.user?.id" :work-groups="workQueue.groups" @retry-work="workQueue.retry" />
  </div>
</template>
