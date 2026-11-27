<script setup lang="ts">
import BusinessSystemAttribution from '@/components/BusinessSystemAttribution.vue'
import RecentEntityActivity from '@/components/RecentEntityActivity.vue'
import DeleteEntityButton from '@/components/DeleteEntityButton.vue'
import CollaborationPeople from '@/components/CollaborationPeople.vue'
import { computed, defineAsyncComponent, onMounted, onScopeDispose, reactive, ref, shallowRef, watch } from 'vue'
import { ElMessage, type UploadRequestOptions } from 'element-plus'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import {
  changeFeedbackStatus,
  convertFeedback,
  createFeedbackComment,
  downloadFeedbackAttachment,
  getFeedback,
  listFeedbackAttachments,
  listFeedbackComments,
  updateFeedback,
  uploadFeedbackAttachment,
} from '@/api/feedbacks'
import { listSystems } from '@/api/systems'
import ScopedObjectSelector from '@/components/ScopedObjectSelector.vue'
import { getRequirement } from '@/api/requirements'
import ScopedRelationLink from '@/components/ScopedRelationLink.vue'
import type { SelectionOption } from '@/composables/useScopedSearch'
import { useDetailNavigation } from '@/composables/useDetailNavigation'
import { usePermission } from '@/composables/usePermission'
import { useAuthStore } from '@/stores/auth'
import type { FeedbackCollaboration } from '@/api/collaboration'
import { actionErrorMessage } from '@/utils/actionError'
import { useEditingPresence } from '@/composables/useEditingPresence'
import { useRevisionConflict } from '@/composables/useRevisionConflict'
import {
  canLinkExistingRequirement as canLinkExistingRequirementFor,
  finishFeedbackConversion,
} from '@/security/detailAuthorization'
import StatusTag from '@/components/StatusTag.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import RevisionConflictDialog from '@/components/RevisionConflictDialog.vue'
import RichTextContent from '@/components/RichTextContent.vue'
import RequirementCreateView from '@/views/requirement/RequirementCreateView.vue'
import { useResponsive } from '@/composables/useResponsive'
import {
  FEEDBACK_TYPES,
  FEEDBACK_URGENCIES,
  availableStatusActions,
  feedbackStatusLabel,
  feedbackStatusTagType,
  feedbackTypeLabel,
  feedbackUrgencyLabel,
  type StatusAction,
} from '@/constants/feedback'
import type {
  AttachmentItem,
  BusinessSystemItem,
  CommentItem,
  ConvertFeedbackPayload,
  Feedback,
  FeedbackUpdatePayload,
  RequirementCreatePayload,
} from '@/types/domain'
import { formatLocalDateTime } from '@/utils/dates'
import { feedbackConflictSummary } from '@/utils/revisionSummaries'
import { plainTextToHtml, richTextPlainText } from '@/utils/richText'
import { isRevisionConflict } from '@/types/revisionConflict'

const RichTextEditor = defineAsyncComponent(() => import('@/components/RichTextEditor.vue'))

const props = defineProps<{ embedded?: boolean; embeddedId?: number }>()
const emit = defineEmits<{ updated: []; close: [] }>()
const route = useRoute()
const router = useRouter()
const { backTo, related } = useDetailNavigation('/feedbacks')
const { can } = usePermission()
const auth = useAuthStore()
const { isMobile } = useResponsive()
const feedbackId = Number(props.embedded ? props.embeddedId : route.params.id)
const { start: startPresence, stop: stopPresence, existingEditor } = useEditingPresence('FEEDBACK', feedbackId)
const conflict = useRevisionConflict()

const item = ref<Feedback | null>(null)
const loading = ref(false)
const activityRefresh = ref(0)
const failed = ref(false)
const attachments = ref<AttachmentItem[]>([])
const comments = ref<CommentItem[]>([])
const systems = ref<BusinessSystemItem[]>([])
const canReadSystems = computed(() => can(['sys.system.view', 'sys.system.manage']))
const canEdit = computed(() => can('rd.feedback.edit') && item.value?.status !== 'ONLINE')
const canEditContent = computed(() => !!item.value && (canEdit.value || (
  can('rd.feedback.view') && item.value.status === 'NEW' && item.value.submitter_id === auth.user?.id
)))
const collaboration = ref<FeedbackCollaboration | null>(null)
const currentCollaboration = computed(() => collaboration.value?.revision === item.value?.revision ? collaboration.value : null)
const delegatedAcceptance = computed(() => !!currentCollaboration.value?.recipients.length && !currentCollaboration.value.recipients.some(p => p.id === auth.user?.id))
const canAccept = computed(() => item.value?.status === 'NEW' && canEdit.value && !!currentCollaboration.value && (!delegatedAcceptance.value || auth.user?.can_view_api_docs === true))
const canAttach = computed(() => can('rd.feedback.create') && item.value?.status !== 'ONLINE')
const canLinkExisting = computed(() => canLinkExistingRequirementFor(can))
const isAccepted = computed(() => item.value?.status === 'ACCEPTED')
const showRequirementGuide = computed(() => item.value?.status === 'REQUIREMENT_LINKED' || item.value?.status === 'ONLINE')
const converted = ref(false)
const canConvert = computed(
  () => can('rd.feedback.convert') && !!item.value && !converted.value && !showRequirementGuide.value && item.value.main_requirement_id == null,
)
const canAcceptAndConvert = computed(() => canAccept.value && canConvert.value)
const canConvertOnly = computed(() => canConvert.value && !canAcceptAndConvert.value
  && (item.value?.status !== 'NEW' || !canEdit.value || !!currentCollaboration.value))
const acceptanceHint = computed(() => {
  if (item.value?.status !== 'NEW' || !canEdit.value) return ''
  if (!currentCollaboration.value) return '请先在“接收与处理”中核对接收人信息。'
  if (!canAccept.value) return '请联系指定接收人受理此反馈；如需调整接收人，可在“接收与处理”中设置。'
  if (!canConvert.value && !converted.value) return '请联系有转需求权限的接收人处理此反馈。'
  return ''
})
const acceptedByName = computed(() => {
  const data = collaboration.value
  if (!data?.accepted_by || data.revision !== item.value?.revision) return ''
  if (data.accepted_by === auth.user?.id) return auth.user.display_name
  return data.recipients.find(person => person.id === data.accepted_by)?.display_name ?? ''
})

async function showConflict(error: unknown, revision: number, onReload?: (latest: Feedback) => void): Promise<void> {
  await conflict.show(error, revision, {
    entityLabel: '反馈',
    getLatest: () => getFeedback(feedbackId),
    summarize: feedbackConflictSummary,
    apply: (latest) => {
      item.value = latest
      onReload?.(latest)
    },
  })
}

const statusActions = computed<StatusAction[]>(() =>
  item.value ? availableStatusActions(item.value.status, canEdit.value) : [],
)
const hasAcceptedActions = computed(() => canConvert.value || statusActions.value.length > 0)
const dispositionLabels: Partial<Record<StatusAction['target'], string>> = {
  DUPLICATE: '标记为重复反馈',
  CLOSED: '关闭反馈',
}

// --- convert to requirement dialog ---
const defaultConfirmPeople = computed(() => auth.user && can('rd.requirement.view')
  ? [{ id: auth.user.id, display_name: auth.user.display_name }]
  : [])
const convertDialog = ref(false)
const convertError = ref('')
const convertEntry = ref<'accept' | 'legacy' | 'create' | 'link'>('legacy')
const convertMode = ref<ConvertFeedbackPayload['type']>('CREATE_NEW')
const isCreateMode = computed(() => convertMode.value === 'CREATE_NEW')
const acceptOnConvert = computed(() => convertEntry.value === 'accept')
const showConvertModes = computed(() => acceptOnConvert.value || convertEntry.value === 'legacy')
const requiresAcceptReason = computed(() => acceptOnConvert.value && delegatedAcceptance.value)
const acceptReason = ref('')
const acceptReasonError = ref('')
const conversionSource = ref<Feedback | null>(null)
const createFormRef = ref<InstanceType<typeof RequirementCreateView>>()
const createSaving = ref(false)
const createExpanded = ref(false)
const linkSubmitting = ref(false)
const convertSubmitting = computed(() => createSaving.value || linkSubmitting.value)
const guidedRequirement = ref<SelectionOption | null>(null)
const selectedRequirementId = ref<number | null>(null)
const convertDialogTitles = { accept: '受理并转需求', legacy: '转为需求', create: '新建需求', link: '关联已有需求' }
let conversionSession: AbortController | null = null
const conversionBlocker = computed(() => {
  if (!conversionSource.value || !item.value) return ''
  if (convertEntry.value === 'legacy' && canConvert.value && !canConvertOnly.value) {
    return canAcceptAndConvert.value ? '当前反馈可由你受理，请从反馈详情打开“受理并转需求”。' : '请先在“接收与处理”中核对接收人信息。'
  }
  if (!acceptOnConvert.value) return ''
  if (item.value.status !== 'NEW') return `反馈状态已变为「${feedbackStatusLabel[item.value.status]}」，请从反馈详情选择当前可用的处理方式。`
  if (!canConvert.value) return '反馈已关联需求或当前账号无转需求权限，请在反馈详情核对。'
  if (!currentCollaboration.value) return '请在“接收与处理”中核对最新接收人信息。'
  if (!canAccept.value) return '当前账号无法受理此反馈，请联系指定接收人处理。'
  return ''
})
const conversionAllowed = computed(() => canConvert.value && !conversionBlocker.value)
const displayedConvertError = computed(() => conversionBlocker.value || convertError.value)
const feedbackConversion = computed(() => conversionSource.value && {
  source: conversionSource.value,
  confirmPeople: defaultConfirmPeople.value,
  allowed: conversionAllowed.value,
  error: displayedConvertError.value,
  submitLabel: acceptOnConvert.value ? '受理并创建需求' : undefined,
  isDirty: () => showConvertModes.value && (acceptReason.value !== '' || selectedRequirementId.value != null),
  busy: linkSubmitting.value,
  validate: validateAcceptanceReason,
  submit: submitFeedbackRequirement,
})

function openConvert(entry: typeof convertEntry.value = 'legacy', requirement: SelectionOption | null = null): void {
  if (!item.value || !canConvert.value || convertDialog.value || convertSubmitting.value) return
  if (entry === 'accept' && !canAcceptAndConvert.value) return
  if (entry === 'legacy' && !canConvertOnly.value) return
  if (entry === 'link' && (!canLinkExisting.value || !requirement)) return
  convertEntry.value = entry
  convertMode.value = entry === 'link' ? 'LINK_EXISTING' : 'CREATE_NEW'
  conversionSource.value = item.value
  guidedRequirement.value = requirement
  selectedRequirementId.value = requirement?.id ?? null
  acceptReason.value = ''
  acceptReasonError.value = ''
  convertError.value = ''
  conversionSession = new AbortController()
  convertDialog.value = true
}

watch(convertDialog, (open) => {
  if (open) return
  conversionSession?.abort()
  conversionSession = null
  createExpanded.value = false
  createSaving.value = false
  linkSubmitting.value = false
}, { flush: 'sync' })
onScopeDispose(() => conversionSession?.abort())
watch(convertMode, () => { convertError.value = '' })
watch([
  () => auth.user?.id,
  () => auth.user?.data_scope,
  () => auth.user?.can_view_api_docs,
  () => Boolean(auth.accessToken),
  () => [...auth.permissionCodes].sort().join(','),
], () => {
  if (!convertDialog.value) return
  guidedRequirement.value = null
  selectedRequirementId.value = null
  conflict.close()
  convertDialog.value = false
}, { flush: 'sync' })
watch(acceptReason, () => { acceptReasonError.value = '' })

async function requestClose(confirmClean = isCreateMode.value): Promise<boolean> {
  if (convertSubmitting.value) return false
  if (!convertDialog.value) return true
  return await createFormRef.value?.requestClose(confirmClean) ?? true
}
defineExpose({ requestClose })
onBeforeRouteUpdate((to, from) => to.path === from.path || requestClose(false))
onBeforeRouteLeave(() => convertEntry.value !== 'link' || requestClose(false))

async function beforeConvertClose(done: () => void): Promise<void> {
  if (await requestClose()) done()
}

async function dismissLink(): Promise<void> {
  if (await requestClose()) convertDialog.value = false
}

async function finishConversion(id: number, message: string): Promise<void> {
  converted.value = true
  emit('updated')
  ElMessage.success(message)
  convertDialog.value = false
  await finishFeedbackConversion(id, can, (path) => router.push(related(path)), load)
}

async function showConversionError(error: unknown, revision: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) return
  const response = (error as { response?: { status?: number; data?: { detail?: unknown } } })?.response
  if (response?.status === 404) {
    convertError.value = acceptOnConvert.value && response.data?.detail === 'Not Found'
      ? '当前服务不支持受理并转需求，请联系管理员检查版本。原输入已保留。'
      : '反馈或目标需求当前无法访问。'
  } else {
    convertError.value = actionErrorMessage(error)
  }
  await showConflict(error, revision, (latest) => {
    if (signal.aborted) return
    if (!acceptOnConvert.value || latest.status === 'NEW') conversionSource.value = latest
    convertError.value = ''
  })
}

function validateAcceptanceReason(): boolean {
  if (!requiresAcceptReason.value) return true
  const length = [...acceptReason.value.trim()].length
  acceptReasonError.value = ''
  if (length < 2) {
    acceptReasonError.value = '请填写至少 2 个字符的代受理原因'
  } else if (length > 500) {
    acceptReasonError.value = '代受理原因最多 500 个字符'
  }
  if (acceptReasonError.value) {
    const mode = isCreateMode.value ? 'create' : 'link'
    document.querySelector<HTMLTextAreaElement>(`[data-accept-reason="${mode}"] textarea`)?.focus()
  }
  return !acceptReasonError.value
}

function acceptancePayload(): Pick<ConvertFeedbackPayload, 'accept_on_convert' | 'accept_reason'> {
  if (!acceptOnConvert.value) return {}
  return {
    accept_on_convert: true,
    ...(requiresAcceptReason.value ? { accept_reason: acceptReason.value.trim() } : {}),
  }
}

async function submitFeedbackRequirement(payload: RequirementCreatePayload): Promise<number | undefined> {
  const feedback = conversionSource.value
  const signal = conversionSession?.signal
  if (!feedback || !signal || !isCreateMode.value || !conversionAllowed.value) return
  if (feedback.system_id != null && payload.system_id != null && feedback.system_id !== payload.system_id) return
  convertError.value = ''
  try {
    const requirement = await convertFeedback(feedback.id, {
      type: 'CREATE_NEW',
      revision: feedback.revision,
      requirement_title: payload.title,
      requirement_type: payload.requirement_type,
      priority: payload.priority,
      description: payload.description,
      description_format: payload.description_format,
      acceptance_criteria: payload.acceptance_criteria,
      participants: payload.participants,
      requirement_id: null,
      ...acceptancePayload(),
      ...(feedback.system_id == null && payload.system_id != null ? { system_id: payload.system_id } : {}),
    }, signal)
    if (!signal.aborted) return requirement.id
  } catch (error) {
    await showConversionError(error, feedback.revision, signal)
  }
}

async function submitLink(): Promise<void> {
  const feedback = conversionSource.value
  const signal = conversionSession?.signal
  const requirementId = selectedRequirementId.value
  if (!feedback || !signal || isCreateMode.value || convertSubmitting.value || !conversionAllowed.value || !canLinkExisting.value) return
  if (!requirementId) {
    ElMessage.warning('请选择目标需求')
    return
  }
  if (!validateAcceptanceReason()) return
  const acceptance = acceptancePayload()
  linkSubmitting.value = true
  convertError.value = ''
  try {
    await getRequirement(requirementId)
    if (signal.aborted || !canLinkExisting.value || !conversionAllowed.value || selectedRequirementId.value !== requirementId) return
    const requirement = await convertFeedback(feedback.id, {
      type: 'LINK_EXISTING',
      revision: feedback.revision,
      priority: 'P2',
      description_format: 'HTML',
      participants: [],
      requirement_id: requirementId,
      ...acceptance,
    }, signal)
    if (!signal.aborted) await finishConversion(requirement.id, acceptOnConvert.value ? '已受理并关联需求' : '已关联需求')
  } catch (error) {
    await showConversionError(error, feedback.revision, signal)
  } finally {
    if (!signal.aborted) linkSubmitting.value = false
  }
}

// --- status change dialog ---
const statusDialog = ref(false)
const statusSubmitting = ref(false)
const currentAction = ref<StatusAction | null>(null)
const statusForm = reactive({ reason: '', duplicate_of_id: null as number | null })
const statusError = ref('')
const statusReasonRequired = computed(() => currentAction.value?.needsReason ?? false)

function openStatusDialog(action: StatusAction): void {
  currentAction.value = action
  statusForm.reason = ''
  statusError.value = ''
  statusForm.duplicate_of_id = null
  statusDialog.value = true
}

function selectDisposition(target: StatusAction['target']): void {
  const action = statusActions.value.find(candidate => candidate.target === target)
  if (action) openStatusDialog(action)
}

async function submitStatus(): Promise<void> {
  if (!item.value || !currentAction.value || statusSubmitting.value || !canEdit.value) return
  const action = currentAction.value
  if (statusReasonRequired.value && !statusForm.reason.trim()) {
    ElMessage.warning('请填写原因')
    return
  }
  if (action.needsDuplicate && !statusForm.duplicate_of_id) {
    ElMessage.warning('请填写重复目标反馈 ID')
    return
  }
  statusSubmitting.value = true; statusError.value = ''
  try {
    if (action.needsDuplicate && statusForm.duplicate_of_id && can('rd.feedback.view')) await getFeedback(statusForm.duplicate_of_id)
    await changeFeedbackStatus(item.value.id, {
      status: action.target,
      revision: item.value.revision,
      reason: statusForm.reason.trim() || null,
      duplicate_of_id: action.needsDuplicate ? statusForm.duplicate_of_id : null,
    })
    emit('updated')
    ElMessage.success('状态已更新')
    statusDialog.value = false
    await load()
  } catch (error) {
    await showConflict(error, item.value.revision, () => { statusDialog.value = false })
    statusError.value = actionErrorMessage(error)
  } finally {
    statusSubmitting.value = false
  }
}

// --- edit dialog ---
const editDialog = ref(false)
const editSubmitting = ref(false)
const editBaseline = shallowRef<Feedback | null>(null)
const editError = ref('')
const editBaselineDescription = computed(() => {
  const source = editBaseline.value
  if (!source) return ''
  return source.description_format === 'HTML' ? source.description : plainTextToHtml(source.description)
})
const editForm = reactive({
  title: '',
  feedback_type: '' as FeedbackUpdatePayload['feedback_type'],
  urgency: '' as FeedbackUpdatePayload['urgency'],
  system_id: null as number | null,
  description: '',
  reproduce_steps: '',
})

function openEdit(): void {
  if (!item.value || !canEditContent.value) return
  fillEditForm(item.value)
  editDialog.value = true
  if (canEdit.value || can('rd.feedback.convert')) void startPresence()
}

function fillEditForm(latest: Feedback): void {
  editBaseline.value = latest
  editError.value = ''
  Object.assign(editForm, {
    title: latest.title,
    feedback_type: latest.feedback_type,
    urgency: latest.urgency,
    system_id: latest.system_id ?? null,
    description: editBaselineDescription.value,
    reproduce_steps: latest.reproduce_steps ?? '',
  })
}

watch(editDialog, (open) => {
  if (!open) void stopPresence()
})

async function submitEdit(): Promise<void> {
  const original = editBaseline.value
  if (!original || !canEditContent.value || editSubmitting.value || conflict.visible) return
  const descriptionChanged = editForm.description !== editBaselineDescription.value
  if (descriptionChanged && Array.from(richTextPlainText(editForm.description)).length < 2) {
    editError.value = '详细描述至少需要 2 个字符'
    return
  }
  editError.value = ''
  editSubmitting.value = true
  try {
    await updateFeedback(original.id, {
      title: editForm.title.trim(),
      feedback_type: editForm.feedback_type,
      urgency: editForm.urgency,
      // Preserve historical modules on ordinary edits; clear only when changing system.
      ...(editForm.system_id !== (original.system_id ?? null)
        ? { system_id: editForm.system_id, module_id: null } : {}),
      ...(descriptionChanged ? { description: editForm.description.trim(), description_format: 'HTML' } : {}),
      reproduce_steps: editForm.reproduce_steps.trim() || null,
      revision: original.revision,
    })
    emit('updated')
    ElMessage.success('反馈已更新')
    editDialog.value = false
    await load()
  } catch (error) {
    await showConflict(error, original.revision, fillEditForm)
    if (!isRevisionConflict(error)) editError.value = actionErrorMessage(error)
  } finally {
    editSubmitting.value = false
  }
}

// --- attachments ---
async function uploadAttachment(options: UploadRequestOptions): Promise<void> {
  await uploadFeedbackAttachment(feedbackId, options.file as File)
  ElMessage.success('附件已上传')
  attachments.value = await listFeedbackAttachments(feedbackId)
}

async function download(att: AttachmentItem): Promise<void> {
  const blob = await downloadFeedbackAttachment(feedbackId, att.file_id)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = att.original_name
  a.click()
  URL.revokeObjectURL(url)
}

// --- comments ---
const commentText = ref('')
const commentSubmitting = ref(false)

async function submitComment(): Promise<void> {
  if (!commentText.value.trim()) return
  commentSubmitting.value = true
  try {
    await createFeedbackComment(feedbackId, commentText.value.trim())
    commentText.value = ''
    comments.value = await listFeedbackComments(feedbackId)
    activityRefresh.value++
  } finally {
    commentSubmitting.value = false
  }
}

async function load(): Promise<void> {
  activityRefresh.value++
  loading.value = true
  failed.value = false
  try {
    item.value = await getFeedback(feedbackId)
    attachments.value = await listFeedbackAttachments(feedbackId)
    comments.value = await listFeedbackComments(feedbackId)
  } catch {
    failed.value = true
    item.value = null
  } finally {
    loading.value = false
  }
}

function onDeleted() {
  emit('updated')
  if (props.embedded) emit('close')
  else void router.replace(backTo.value)
}

onMounted(async () => {
  if (canReadSystems.value) {
    try {
      const data = await listSystems()
      systems.value = data.systems
    } catch {
      // Optional display enrichment.
    }
  }
  await load()
})
</script>

<template>
  <section v-loading="loading" class="page">
    <ErrorState v-if="failed" title="反馈加载失败" description="请检查网络或确认反馈是否仍可访问。" retry-label="重新加载" @retry="load" />
    <template v-if="item">

      <PageHeader :title="item.title" :eyebrow="item.feedback_no">
        <template #status>
          <StatusTag :status="item.status" :label="feedbackStatusLabel[item.status]" :type="feedbackStatusTagType(item.status)" />
        </template>
        <template #actions>
          <RouterLink v-if="!props.embedded" class="back-link" :to="backTo">返回列表</RouterLink>
          <el-button v-if="canEditContent" @click="openEdit">编辑</el-button>
          <DeleteEntityButton v-if="canEdit && item.status === 'NEW' && !item.main_requirement_id" kind="feedbacks" :id="item.id" :revision="item.revision" :title="item.title" @refresh="load" @deleted="onDeleted" />
          <template v-if="!isAccepted">
            <el-button v-if="canAcceptAndConvert" type="primary" @click="openConvert('accept')">受理并转需求</el-button>
            <el-button v-else-if="canConvertOnly" type="primary" @click="openConvert()">转需求</el-button>
            <el-button
              v-for="action in statusActions"
              :key="action.target"
              type="primary"
              plain
              @click="openStatusDialog(action)"
            >
              {{ action.label }}
            </el-button>
          </template>
        </template>
      </PageHeader>

      <section v-if="isAccepted || showRequirementGuide" class="feedback-guide" :class="{ 'feedback-guide--actionable': isAccepted && hasAcceptedActions }">
        <template v-if="isAccepted">
          <div class="feedback-guide__summary">
            <h2>{{ hasAcceptedActions ? '下一步处理' : '受理进度' }}</h2>
            <p>{{ acceptedByName ? `${acceptedByName} 已受理此反馈` : '反馈已受理' }}{{ canConvert ? '。涉及研发的反馈可通过需求跟进。' : '，正在跟进。' }}</p>
          </div>
          <div v-if="hasAcceptedActions" class="feedback-guide__actions">
            <el-button v-if="canConvert" type="primary" @click="openConvert('create')">新建需求</el-button>
            <ScopedObjectSelector
              v-if="canConvert && canLinkExisting"
              kind="requirement"
              :allowed="canLinkExisting"
              :active="true"
              :disabled="convertSubmitting"
              @selected="openConvert('link', $event)"
            >
              <template #trigger="{ open, disabled }">
                <el-button :disabled="disabled" @click="open">关联已有需求</el-button>
              </template>
            </ScopedObjectSelector>
            <el-dropdown v-if="statusActions.length" trigger="click" @command="selectDisposition">
              <el-button>更多处理<span class="feedback-guide__chevron" aria-hidden="true"></span></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="action in statusActions" :key="action.target" :command="action.target">
                    {{ dispositionLabels[action.target] ?? action.label }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
        <div v-else class="feedback-guide__summary">
          <h2>关联需求</h2>
          <p v-if="item.main_requirement_id == null">暂无关联需求记录</p>
          <ScopedRelationLink
            v-else
            kind="requirement"
            :id="item.main_requirement_id"
            :return-to="backTo"
            :parent-identity="String(item.id)"
            fallback="当前无法查看关联需求"
          />
        </div>
      </section>

      <BusinessSystemAttribution :system-id="item.system_id" :system-name="item.system_name" />
      <p v-if="acceptanceHint" class="acceptance-hint" role="status">{{ acceptanceHint }}</p>
      <CollaborationPeople v-if="can('rd.feedback.view')" kind="feedback" :id="item.id" :revision="item.revision" :editable="canEdit" @loaded="collaboration = $event" @updated="load" />

      <div class="detail-grid">
      <SectionCard title="反馈详情" description="问题内容与复现信息" class="detail-main">
        <el-descriptions :column="isMobile ? 1 : 2">
          <el-descriptions-item label="类型">
            {{ feedbackTypeLabel[item.feedback_type] ?? item.feedback_type }}
          </el-descriptions-item>
          <el-descriptions-item label="紧急程度">
            {{ feedbackUrgencyLabel[item.urgency] ?? item.urgency }}
          </el-descriptions-item>
          <el-descriptions-item label="详细描述" :span="isMobile ? 1 : 2">
            <RichTextContent :feedback-id="item.id" :content="item.description" :format="item.description_format" />
          </el-descriptions-item>
          <el-descriptions-item v-if="item.expected_result" label="历史补充 · 期望结果" :span="isMobile ? 1 : 2">
            <div class="multiline">{{ item.expected_result }}</div>
          </el-descriptions-item>
          <el-descriptions-item v-if="item.actual_result" label="历史补充 · 实际结果" :span="isMobile ? 1 : 2">
            <div class="multiline">{{ item.actual_result }}</div>
          </el-descriptions-item>
          <el-descriptions-item v-if="item.reproduce_steps" label="复现步骤" :span="isMobile ? 1 : 2">
            <div class="multiline">{{ item.reproduce_steps }}</div>
          </el-descriptions-item>
        </el-descriptions>
      </SectionCard>
      <SectionCard title="流转信息" description="关联对象与记录时间" class="detail-side">
        <dl class="side-fields">
          <div v-if="!showRequirementGuide"><dt>关联需求</dt><dd><ScopedRelationLink kind="requirement" :id="item.main_requirement_id" :return-to="backTo" :parent-identity="String(item.id)" /></dd></div>
          <div v-if="item.duplicate_of_id"><dt>重复于</dt><dd><ScopedRelationLink kind="feedback" :id="item.duplicate_of_id" :return-to="backTo" :parent-identity="String(item.id)" /></dd></div>
          <div><dt>提交人</dt><dd>{{ item.submitter_display_name || '未知用户' }}</dd></div>
          <div><dt>创建时间</dt><dd>{{ formatLocalDateTime(item.created_at) }}</dd></div>
          <div><dt>更新时间</dt><dd>{{ formatLocalDateTime(item.updated_at) }}</dd></div>
        </dl>
      </SectionCard>
      </div>

      <RecentEntityActivity kind="feedback" :id="item.id" :revision="item.revision" :refresh-key="activityRefresh" />

      <!-- attachments -->
      <SectionCard title="附件" class="section">
        <template #actions>
          <el-upload
            v-if="canAttach"
            :show-file-list="false"
            :http-request="uploadAttachment"
          >
            <el-button size="small">上传附件</el-button>
          </el-upload>
        </template>
        <ul v-if="attachments.length" class="attachments">
          <li v-for="a in attachments" :key="a.file_id">
            <el-link type="primary" @click="download(a)">{{ a.original_name }}</el-link>
            <span class="att-size">{{ Math.max(1, Math.round(a.size / 1024)) }} KB</span>
          </li>
        </ul>
        <EmptyState v-else description="暂无附件" compact />
      </SectionCard>

      <!-- comments -->
      <SectionCard title="评论" class="section">
        <ul v-if="comments.length" class="comments">
          <li v-for="c in comments" :key="c.id">
            <div class="comment-meta">#{{ c.created_by }} · {{ formatLocalDateTime(c.created_at) }}</div>
            <div class="multiline">{{ c.content }}</div>
          </li>
        </ul>
        <EmptyState v-else description="暂无评论" compact />
        <div v-if="item.status !== 'ONLINE'" class="comment-form">
          <el-input v-model="commentText" type="textarea" :rows="2" placeholder="写下评论…" />
          <el-button
            type="primary"
            :loading="commentSubmitting"
            :disabled="!commentText.trim()"
            @click="submitComment"
          >
            发表
          </el-button>
        </div>
      </SectionCard>
    </template>

    <!-- status change dialog -->
    <el-dialog
      v-model="statusDialog"
      :title="currentAction?.label ?? '状态变更'"
      width="min(480px, 92vw)"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item v-if="currentAction?.needsDuplicate" label="重复目标反馈 ID" required>
          <ScopedObjectSelector v-model="statusForm.duplicate_of_id" kind="feedback" :allowed="can('rd.feedback.view')" :active="statusDialog" :disabled="statusSubmitting" :exclude-id="feedbackId" />
        </el-form-item>
        <el-form-item v-if="statusReasonRequired" label="原因" required>
          <el-input v-model="statusForm.reason" type="textarea" :rows="3" />
        </el-form-item>
        <p v-if="currentAction && !statusReasonRequired && !currentAction.needsDuplicate">
          确认将反馈状态改为「{{ feedbackStatusLabel[currentAction.target] }}」？
        </p>
        <p v-if="statusError" role="alert">{{ statusError }}</p>
      </el-form>
      <template #footer>
        <el-button @click="statusDialog = false">取消</el-button>
        <el-button type="primary" :loading="statusSubmitting" @click="submitStatus">确定</el-button>
      </template>
    </el-dialog>

    <RevisionConflictDialog
      :visible="conflict.visible"
      :loading="conflict.loading"
      :entity-label="conflict.entityLabel"
      :submitted-revision="conflict.submittedRevision"
      :metadata="conflict.metadata"
      :summary="conflict.summary"
      :read-error="conflict.readError"
      @close="conflict.close"
      @reload="conflict.reload"
    />

    <!-- edit dialog -->
    <el-dialog
      v-model="editDialog"
      title="编辑反馈"
      width="min(560px, 92vw)"
      destroy-on-close
      :close-on-click-modal="!editSubmitting"
      :close-on-press-escape="!editSubmitting"
      :show-close="!editSubmitting"
    >
      <el-alert v-if="existingEditor" type="warning" :closable="false" show-icon class="presence-alert">
        <template #title>{{ existingEditor.display_name }} 正在编辑此反馈</template>
        你仍可继续编辑；如数据已变化，保存时会通过 revision 冲突保护避免静默覆盖。
      </el-alert>
      <el-form label-position="top" :disabled="editSubmitting" @submit.prevent="submitEdit">
        <el-form-item label="反馈类型">
          <el-select v-model="editForm.feedback_type" style="width: 100%">
            <el-option v-for="t in FEEDBACK_TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="editForm.title" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="紧急程度">
          <el-radio-group v-model="editForm.urgency">
            <el-radio v-for="u in FEEDBACK_URGENCIES" :key="u.value" :value="u.value">
              {{ u.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="canReadSystems">
          <el-form-item label="所属系统">
            <el-select
              v-model="editForm.system_id"
              clearable
              placeholder="可选"
              style="width: 100%"
            >
              <el-option v-for="s in systems" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
          </el-form-item>
        </template>
        <el-form-item label="详细描述">
          <RichTextEditor
            :key="editBaseline?.revision"
            v-model="editForm.description"
            :feedback-id="editBaseline?.id"
            :disabled="editSubmitting"
            label="详细描述"
          />
        </el-form-item>
        <el-form-item label="复现步骤">
          <el-input v-model="editForm.reproduce_steps" type="textarea" :rows="3" />
        </el-form-item>
        <p v-if="editError" class="edit-error" role="alert">{{ editError }}</p>
      </el-form>
      <template #footer>
        <el-button :disabled="editSubmitting" @click="editDialog = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" :disabled="!canEditContent" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- convert to requirement dialog -->
    <el-dialog
      v-model="convertDialog"
      :title="convertDialogTitles[convertEntry]"
      :class="{ 'create-dialog': isCreateMode }"
      :width="isCreateMode ? 'min(1040px, calc(100vw - 32px))' : 'min(560px, 92vw)'"
      :fullscreen="isCreateMode && createExpanded"
      :before-close="beforeConvertClose"
      :close-on-click-modal="!isCreateMode && !acceptOnConvert && !convertSubmitting"
      :close-on-press-escape="!convertSubmitting"
      :show-close="!convertSubmitting"
      append-to-body
      destroy-on-close
    >
      <template v-if="showConvertModes" #header="{ titleId, titleClass }">
        <div>
          <span :id="titleId" :class="titleClass">{{ convertDialogTitles[convertEntry] }}</span>
          <div class="convert-mode">
            <span>转换方式</span>
            <el-radio-group v-model="convertMode" aria-label="转换方式" :disabled="convertSubmitting">
              <el-radio value="CREATE_NEW">新建需求</el-radio>
              <el-radio v-if="canLinkExisting" value="LINK_EXISTING">关联已有需求</el-radio>
            </el-radio-group>
          </div>
        </div>
      </template>
      <RequirementCreateView
        v-if="convertDialog && feedbackConversion && convertEntry !== 'link'"
        v-show="isCreateMode"
        ref="createFormRef"
        embedded
        :conversion="feedbackConversion"
        @cancel="convertDialog = false"
        @created="finishConversion($event, acceptOnConvert ? '已受理并创建需求' : '已转为需求')"
        @saving="createSaving = $event"
        @expanded="createExpanded = $event"
      >
        <template v-if="requiresAcceptReason" #additional-fields>
          <el-form-item label="代受理原因（必填）" required :error="acceptReasonError" class="span-2" data-accept-reason="create">
            <el-input v-model="acceptReason" type="textarea" :rows="2" :maxlength="500" />
          </el-form-item>
        </template>
      </RequirementCreateView>
      <el-form v-if="!isCreateMode" label-position="top" :disabled="convertSubmitting" @submit.prevent="submitLink">
        <el-form-item v-if="convertEntry === 'link' && guidedRequirement" label="目标需求">
          <span class="multiline">{{ guidedRequirement.code }} · {{ guidedRequirement.title }}</span>
        </el-form-item>
        <el-form-item v-else-if="showConvertModes" label="目标需求" required>
          <ScopedObjectSelector v-model="selectedRequirementId" kind="requirement" :allowed="canLinkExisting" :active="convertDialog" :disabled="convertSubmitting" />
        </el-form-item>
        <el-form-item v-if="requiresAcceptReason" label="代受理原因（必填）" required :error="acceptReasonError" data-accept-reason="link">
          <el-input v-model="acceptReason" type="textarea" :rows="2" :maxlength="500" />
        </el-form-item>
        <p v-if="displayedConvertError" class="convert-error" role="alert">{{ displayedConvertError }}</p>
      </el-form>
      <template v-if="!isCreateMode" #footer>
        <el-button :disabled="convertSubmitting" @click="dismissLink">取消</el-button>
        <el-button type="primary" :loading="convertSubmitting" :disabled="!conversionAllowed || !canLinkExisting" @click="submitLink">{{ acceptOnConvert ? '受理并关联已有需求' : '确定' }}</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.back-link { color: var(--if-brand-500); align-self: center; }
.feedback-guide {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--if-space-3) var(--if-space-5);
  margin-bottom: var(--if-space-4);
  padding: var(--if-space-3) var(--if-space-4);
  border: 1px solid var(--if-border);
  border-radius: var(--if-radius);
  background: var(--if-bg-surface);
}
.feedback-guide--actionable {
  border-color: var(--if-info-border);
  background: var(--if-info-bg);
}
.feedback-guide__summary {
  flex: 1 1 250px;
  min-width: 0;
  color: var(--if-text-2);
  font-size: var(--if-font-body);
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.feedback-guide__summary h2 { margin: 0 0 var(--if-space-1); color: var(--if-text-1); font-size: var(--if-font-section); }
.feedback-guide__summary p { margin: 0; }
.feedback-guide__actions { display: flex; flex-wrap: wrap; gap: var(--if-space-2); min-width: 0; }
.feedback-guide__actions :deep(.el-button) { margin: 0; }
.feedback-guide__chevron {
  margin-left: var(--if-space-2);
  width: 6px;
  height: 6px;
  border: solid currentColor;
  border-width: 0 1.5px 1.5px 0;
  transform: translateY(-2px) rotate(45deg);
}
.convert-error, .edit-error { color: var(--if-danger-fg); overflow-wrap: anywhere; }
.acceptance-hint { margin: var(--if-space-3) 0; color: var(--if-text-2); }
.convert-mode { display: flex; flex-wrap: wrap; align-items: center; gap: 0 var(--if-space-3); margin-top: var(--if-space-2); }
.detail-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(250px, 300px); align-items: start; gap: var(--if-space-4); }
.detail-main, .detail-side { min-width: 0; }
.detail-grid > .detail-main + .detail-side { margin-top: 0; }
.detail-main :deep(.el-descriptions__body), .detail-main :deep(.el-descriptions__table) { width: 100%; }
.detail-main :deep(.el-descriptions__label) { color: var(--if-text-3); font-size: 12px; }
.detail-main :deep(.el-descriptions__content) { color: var(--if-text-1); overflow-wrap: anywhere; }
.multiline { white-space: pre-wrap; overflow-wrap: anywhere; }
.side-fields { display: grid; gap: 13px; margin: 0; }
.side-fields > div { min-width: 0; padding-bottom: 12px; border-bottom: 1px solid var(--if-border); }
.side-fields > div:last-child { border-bottom: 0; padding-bottom: 0; }
.side-fields dt { margin-bottom: 4px; color: var(--if-text-3); font-size: 12px; }
.side-fields dd { margin: 0; color: var(--if-text-1); font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }
.section { margin-top: var(--if-space-4); }
.attachments, .comments { list-style: none; margin: 0; padding: 0; }
.attachments li { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 9px 0; border-bottom: 1px solid var(--if-border); }
.attachments li:last-child { border-bottom: 0; }
.att-size { color: var(--if-text-3); font-size: 12px; }
.comments li { padding: 12px 0; border-bottom: 1px solid var(--if-border); }
.comment-meta { color: var(--if-text-3); font-size: 12px; margin-bottom: 4px; }
.comment-form { display: flex; gap: 8px; align-items: flex-start; margin-top: 16px; }
.comment-form .el-button { flex-shrink: 0; }
.presence-alert { min-width: 0; margin-bottom: var(--if-space-4); overflow-wrap: anywhere; }
.presence-alert :deep(.el-alert__content), .presence-alert :deep(.el-alert__title) { min-width: 0; overflow-wrap: anywhere; }
@media (max-width: 1199px) { .detail-grid { grid-template-columns: 1fr; } }
@media (max-width: 767px) {
  .feedback-guide__actions :deep(.el-button) { min-height: 44px; }
  .comment-form { flex-direction: column; }
  .comment-form .el-button { align-self: flex-end; }
}
</style>
