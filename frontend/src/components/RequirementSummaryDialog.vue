<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { getRequirement, listRequirementFeedbacks } from '@/api/requirements'
import { useAuthStore } from '@/stores/auth'
import { useResponsive } from '@/composables/useResponsive'
import { detailTarget } from '@/utils/listQuery'
import { requirementStatusLabel, requirementTypeLabel } from '@/constants/requirement'
import type { LinkedFeedback, Requirement } from '@/types/domain'

const props = defineProps<{ id: number | null; returnTo: string }>()
const emit = defineEmits<{ close: [] }>()
const auth = useAuthStore()
const { isMobile } = useResponsive()
const item = ref<Requirement | null>(null)
const feedbacks = ref<LinkedFeedback[]>([])
const loading = ref(false)
const failed = ref(false)
const feedbacksFailed = ref(false)
const retry = ref(0)
let sequence = 0
const identity = computed(() => `${auth.user?.id}:${auth.accessToken}:${auth.permissionCodes.join(',')}`)

watch(() => [props.id, identity.value, retry.value] as const, async ([id]) => {
  const current = ++sequence
  item.value = null
  feedbacks.value = []
  failed.value = false
  feedbacksFailed.value = false
  loading.value = false
  if (id == null) return
  if (!auth.hasPermission('rd.requirement.view')) { failed.value = true; return }
  loading.value = true
  try {
    const result = await getRequirement(id)
    if (current !== sequence) return
    if (result.id !== id) throw new Error('Requirement identity changed')
    item.value = result
  } catch {
    if (current === sequence) failed.value = true
  } finally {
    if (current === sequence) loading.value = false
  }
  if (current !== sequence || !item.value || !auth.hasPermission('rd.feedback.view')) return
  try {
    const result = await listRequirementFeedbacks(id)
    if (current === sequence) feedbacks.value = result
  } catch {
    if (current === sequence) feedbacksFailed.value = true
  }
}, { immediate: true, flush: 'sync' })

onScopeDispose(() => { sequence++ })
</script>

<template>
  <el-dialog :model-value="id !== null" title="需求摘要" class="requirement-summary-dialog" modal-class="requirement-summary-overlay" width="min(760px, 92vw)" :fullscreen="isMobile" append-to-body destroy-on-close @update:model-value="!$event && emit('close')">
    <div v-if="loading" role="status">正在加载需求…</div>
    <div v-else-if="failed" role="alert">
      <p>需求暂时无法查看，请检查网络或访问权限。</p>
      <el-button @click="retry++">重新加载</el-button>
    </div>
    <article v-else-if="item" class="requirement-summary">
      <p class="summary-number">{{ item.requirement_no }}</p>
      <h2>{{ item.title }}</h2>
      <el-descriptions :column="isMobile ? 1 : 2">
        <el-descriptions-item label="状态">{{ requirementStatusLabel[item.status] }}</el-descriptions-item>
        <el-descriptions-item label="优先级">{{ item.priority }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ requirementTypeLabel[item.requirement_type] || item.requirement_type }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ item.source === 'FEEDBACK' ? '反馈转化' : '直接创建' }}</el-descriptions-item>
      </el-descriptions>
      <h3>需求描述</h3>
      <p class="summary-content">{{ item.description || '暂无描述' }}</p>
      <h3>验收标准</h3>
      <p class="summary-content">{{ item.acceptance_criteria || '尚未填写' }}</p>
      <template v-if="auth.hasPermission('rd.feedback.view')">
        <h3>来源反馈</h3>
        <p v-if="feedbacksFailed">来源反馈暂时无法加载。</p>
        <ul v-else-if="feedbacks.length">
          <li v-for="feedback in feedbacks" :key="feedback.feedback_id">
            <RouterLink :to="detailTarget(`/feedbacks/${feedback.feedback_id}`, returnTo)" @click="emit('close')">{{ feedback.feedback_no }} · {{ feedback.title }}</RouterLink>
          </li>
        </ul>
        <p v-else>暂无可见来源反馈</p>
      </template>
    </article>
    <template #footer>
      <el-button @click="emit('close')">关闭</el-button>
      <RouterLink v-if="item" class="summary-detail-link" :to="detailTarget(`/requirements/${item.id}`, returnTo)" @click="emit('close')">打开完整详情</RouterLink>
    </template>
  </el-dialog>
</template>

<style scoped>
.requirement-summary { overflow-wrap: anywhere; }
.summary-number { color: var(--if-text-3); }
h2 { font-size: 20px; margin: 8px 0 20px; }
h3 { font-size: 14px; margin: 20px 0 8px; }
.summary-content { white-space: pre-wrap; line-height: 1.7; }
.summary-detail-link { display: inline-block; padding: 10px 12px; margin-left: 12px; color: var(--if-brand-500); }
.summary-detail-link:focus-visible { outline: 2px solid var(--if-brand-500); outline-offset: 2px; }
li { margin: 8px 0; }
@media (max-width: 767px) {
  :global(.requirement-summary-overlay .el-overlay-dialog) { padding: 0; }
  :global(.requirement-summary-dialog.is-fullscreen) {
    width: 100vw !important;
    max-width: 100vw;
    height: 100dvh;
    max-height: 100dvh;
    border: 0;
    border-radius: 0;
    padding-bottom: env(safe-area-inset-bottom);
  }
}
</style>
