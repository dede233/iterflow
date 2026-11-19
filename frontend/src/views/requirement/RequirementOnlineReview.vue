<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref, useId } from 'vue'
import { ElMessage } from 'element-plus'
import { confirmOnlineReview, getOnlineReview } from '@/api/requirements'
import StatusTag from '@/components/StatusTag.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import { usePermission } from '@/composables/usePermission'
import { useResponsive } from '@/composables/useResponsive'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import { feedbackStatusLabel, feedbackStatusTagType } from '@/constants/feedback'
import type { Requirement } from '@/types/domain'
import { isRevisionConflict } from '@/types/revisionConflict'
import { actionErrorMessage } from '@/utils/actionError'
import { formatLocalDateTime } from '@/utils/dates'
import { detailTarget } from '@/utils/listQuery'

const FeedbackCreateView = defineAsyncComponent(() => import('@/views/feedback/FeedbackCreateView.vue'))
const props = defineProps<{ item: Requirement; returnTo: string }>()
const emit = defineEmits<{ updated: [] }>()
const { can } = usePermission()
const { isMobile } = useResponsive()
const canViewFeedback = computed(() => can('rd.feedback.view'))
const canCreateFeedback = computed(() => can('rd.feedback.create'))
const pageSize = 10
const page = ref(1)
const loading = ref(true)
const failed = ref(false)
const review = ref<Awaited<ReturnType<typeof getOnlineReview>> | null>(null)
const confirmDescriptionId = useId()

async function load(targetPage = page.value) {
  loading.value = true
  failed.value = false
  page.value = targetPage
  try {
    const latest = await getOnlineReview(props.item.id, targetPage)
    const lastPage = Math.max(1, Math.ceil(latest.feedback_total / pageSize))
    if (targetPage > lastPage) page.value = lastPage
    review.value = targetPage > lastPage ? await getOnlineReview(props.item.id, lastPage) : latest
    return review.value
  } catch {
    failed.value = true
    review.value = null
    return null
  } finally {
    loading.value = false
  }
}

function changePage(targetPage: number): void {
  if (!loading.value && targetPage !== page.value) void load(targetPage)
}

async function refreshRevision(): Promise<number> {
  const latest = await load()
  if (!latest) throw new Error('需求信息刷新失败')
  return latest.revision
}

const confirmDialog = ref(false)
const confirmNote = ref('')
const confirmRevision = ref(0)
const confirmError = ref('')
const confirmNeedsRefresh = ref(false)
const confirming = ref(false)
const confirmRefreshing = ref(false)
const confirmBusy = computed(() => confirming.value || confirmRefreshing.value)
const confirmDraft = useUnsavedChanges({
  active: () => confirmDialog.value,
  isDirty: () => confirmNote.value !== '',
  isBusy: () => confirmBusy.value,
})

function openConfirmation(): void {
  if (loading.value || !review.value?.can_confirm) return
  confirmNote.value = ''
  confirmError.value = ''
  confirmNeedsRefresh.value = false
  confirmRevision.value = review.value.revision
  confirmDialog.value = true
}

async function closeConfirmation(): Promise<boolean> {
  if (!(await confirmDraft.requestLeave())) return false
  confirmDialog.value = false
  return true
}

async function beforeConfirmationClose(done: () => void): Promise<void> {
  if (await closeConfirmation()) done()
}

async function refreshConfirmation(): Promise<void> {
  if (confirmBusy.value) return
  confirmRefreshing.value = true
  try {
    confirmRevision.value = await refreshRevision()
    confirmNeedsRefresh.value = false
    confirmError.value = review.value?.can_confirm ? '' : (review.value?.confirmation ? '线上效果已确认。' : '当前账号无法确认线上效果。')
  } catch {
    confirmError.value = '暂时无法刷新需求信息，已保留你的输入。'
  } finally {
    confirmRefreshing.value = false
  }
}

async function submitConfirmation(): Promise<void> {
  if (confirmBusy.value || confirmNeedsRefresh.value || !review.value?.can_confirm) return
  confirming.value = true
  confirmError.value = ''
  try {
    const confirmation = await confirmOnlineReview(props.item.id, {
      revision: confirmRevision.value,
      note: confirmNote.value.trim() || null,
    })
    review.value = { ...review.value, can_confirm: false, confirmation }
    confirmDialog.value = false
    emit('updated')
    ElMessage.success('线上效果已确认')
    await load()
  } catch (error) {
    confirmNeedsRefresh.value = isRevisionConflict(error)
    confirmError.value = confirmNeedsRefresh.value
      ? '需求信息已更新。请刷新需求信息后重新确认，已保留你的说明。'
      : actionErrorMessage(error)
  } finally {
    confirming.value = false
  }
}

const feedbackDialog = ref(false)
const feedbackBusy = ref(false)
const feedbackRevision = ref(0)
const feedbackForm = ref<InstanceType<typeof FeedbackCreateView>>()

function openFeedback(): void {
  if (loading.value || !review.value || !canCreateFeedback.value) return
  feedbackRevision.value = review.value.revision
  feedbackDialog.value = true
}

async function closeFeedback(): Promise<boolean> {
  if (!feedbackDialog.value) return true
  if (feedbackBusy.value || (feedbackForm.value && !(await feedbackForm.value.requestClose()))) return false
  feedbackDialog.value = false
  return true
}

async function beforeFeedbackClose(done: () => void): Promise<void> {
  if (await closeFeedback()) done()
}

function onFeedbackRecorded(): void {
  emit('updated')
  void load(1)
}

async function requestClose(): Promise<boolean> {
  return await closeFeedback() && await closeConfirmation()
}

defineExpose({ requestClose })
onMounted(() => load())
</script>

<template>
  <SectionCard title="线上效果确认" class="online-review">
    <template v-if="review" #actions>
      <el-button
        v-if="!review.confirmation"
        type="primary"
        :disabled="loading || !review.can_confirm"
        :aria-describedby="!review.can_confirm ? confirmDescriptionId : undefined"
        @click="openConfirmation"
      >确认无误</el-button>
      <el-button v-if="canCreateFeedback" :disabled="loading" @click="openFeedback">提交线上反馈</el-button>
    </template>

    <div v-if="failed" class="load-error" role="alert">
      <p>暂时无法读取线上效果确认记录。</p>
      <el-button @click="load()">重新加载</el-button>
    </div>
    <p v-else-if="!review" role="status" class="muted">正在加载线上效果确认记录…</p>
    <template v-else>
      <div class="review-summary" aria-live="polite">
        <el-tag :type="review.confirmation ? 'success' : 'info'">{{ review.confirmation ? '已确认' : '待确认' }}</el-tag>
        <template v-if="review.confirmation">
          <span>{{ review.confirmation.confirmed_by_name }}</span>
          <time class="muted" :datetime="review.confirmation.confirmed_at">{{ formatLocalDateTime(review.confirmation.confirmed_at) }}</time>
          <p v-if="review.confirmation.note" class="confirmation-note">{{ review.confirmation.note }}</p>
        </template>
        <span v-else-if="review.can_confirm" class="muted">请验证线上效果后确认。</span>
        <span v-else :id="confirmDescriptionId" class="muted">仅需求创建人可确认线上效果。</span>
      </div>

      <div v-if="canViewFeedback" v-loading="loading" class="feedback-section" :aria-busy="loading">
        <h3>线上反馈 <span v-if="review.feedback_total" class="muted">共 {{ review.feedback_total }} 条</span></h3>
        <ul v-if="review.feedbacks.length" class="feedback-list">
          <li v-for="feedback in review.feedbacks" :key="feedback.id">
            <RouterLink :to="detailTarget(`/feedbacks/${feedback.id}`, props.returnTo)">
              {{ feedback.feedback_no }} · {{ feedback.title }}
            </RouterLink>
            <div class="feedback-meta">
              <StatusTag :status="feedback.status" :label="feedbackStatusLabel[feedback.status]" :type="feedbackStatusTagType(feedback.status)" size="sm" />
              <time class="muted" :datetime="feedback.created_at">{{ formatLocalDateTime(feedback.created_at) }}</time>
            </div>
          </li>
        </ul>
        <p v-else class="muted">暂无可见线上反馈</p>
        <el-pagination
          v-if="review.feedback_total > pageSize"
          class="feedback-pagination"
          layout="prev, pager, next"
          aria-label="线上反馈分页"
          :current-page="page"
          :page-size="pageSize"
          :pager-count="5"
          :total="review.feedback_total"
          :disabled="loading"
          @current-change="changePage"
        />
      </div>
    </template>
  </SectionCard>

  <el-dialog
    v-model="confirmDialog"
    title="确认线上效果"
    width="min(480px, calc(100vw - 32px))"
    append-to-body
    destroy-on-close
    :before-close="beforeConfirmationClose"
    :close-on-click-modal="false"
    :close-on-press-escape="!confirmBusy"
    :show-close="!confirmBusy"
  >
    <p class="confirm-intro">请在实际验证线上效果后确认。</p>
    <el-form label-position="top" :disabled="confirmBusy" @submit.prevent="submitConfirmation">
      <el-form-item label="确认说明（选填）">
        <el-input v-model="confirmNote" type="textarea" :rows="3" maxlength="500" show-word-limit />
      </el-form-item>
    </el-form>
    <div v-if="confirmError" class="submit-error">
      <p role="alert">{{ confirmError }}</p>
      <el-button v-if="confirmNeedsRefresh" plain type="primary" :loading="confirmRefreshing" @click="refreshConfirmation">刷新需求信息</el-button>
    </div>
    <template #footer>
      <el-button :disabled="confirmBusy" @click="closeConfirmation">取消</el-button>
      <el-button type="primary" :loading="confirming" :disabled="confirmNeedsRefresh || confirmRefreshing || !review?.can_confirm" @click="submitConfirmation">确认无误</el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="feedbackDialog"
    title="提交线上反馈"
    class="create-dialog"
    width="min(860px, calc(100vw - 24px))"
    :fullscreen="isMobile"
    append-to-body
    destroy-on-close
    :before-close="beforeFeedbackClose"
    :close-on-click-modal="false"
    :close-on-press-escape="!feedbackBusy"
    :show-close="!feedbackBusy"
  >
    <FeedbackCreateView
      v-if="feedbackDialog"
      ref="feedbackForm"
      embedded
      :online-review="{ id: props.item.id, number: props.item.requirement_no, title: props.item.title, revision: feedbackRevision, refreshRevision }"
      @cancel="feedbackDialog = false"
      @created="feedbackDialog = false"
      @recorded="onFeedbackRecorded"
      @saving="feedbackBusy = $event"
    />
  </el-dialog>
</template>

<style scoped>
.online-review { margin-block-end: var(--if-space-4); }
.review-summary { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; overflow-wrap: anywhere; }
.muted { color: var(--if-text-3); font-size: var(--if-font-caption); font-weight: 400; }
.confirmation-note { flex-basis: 100%; margin: 2px 0 0; white-space: pre-wrap; }
.feedback-section { border-top: 1px solid var(--if-border); margin-top: 14px; padding-top: 12px; }
.feedback-section h3 { margin: 0 0 4px; font-size: var(--if-font-body); }
.feedback-section h3 span { margin-inline-start: 8px; }
.feedback-list { list-style: none; margin: 0; padding: 0; }
.feedback-list li { display: flex; flex-wrap: wrap; gap: 4px 16px; align-items: baseline; padding: 8px 0; border-bottom: 1px solid var(--if-border); }
.feedback-list a { flex: 1 1 16rem; min-width: 0; overflow-wrap: anywhere; color: var(--if-brand-500); }
.feedback-list a:focus-visible { outline: 2px solid var(--if-brand-500); outline-offset: 2px; }
.feedback-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; }
.feedback-pagination { margin-top: 10px; }
.load-error { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; }
.load-error p { margin: 0; }
.confirm-intro { margin: 0 0 14px; color: var(--if-text-2); }
.submit-error p { margin: 0 0 8px; color: var(--el-color-danger); overflow-wrap: anywhere; }
</style>
