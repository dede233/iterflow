<script setup lang="ts">
import { computed, onScopeDispose, ref, useId, watch } from 'vue'
import { actWorkflow, getWorkflow, getParticipants, type Workflow, type WorkflowAction, type Participants, type Participant } from '@/api/collaboration'
import { useAuthStore } from '@/stores/auth'
import { availableRequirementStatusActions, requirementStatusLabel, type ReqStatusAction } from '@/constants/requirement'
import { formatLocalDateTime } from '@/utils/dates'
import { actionErrorMessage } from '@/utils/actionError'
import type { Requirement } from '@/types/domain'
import RequirementPeopleDialog from './RequirementPeopleDialog.vue'
import RichTextContent from './RichTextContent.vue'
import SectionCard from './ui/SectionCard.vue'
const props = defineProps<{ item: Requirement; readonly?: boolean }>()
const emit = defineEmits<{ updated: []; status: [action: ReqStatusAction] }>()
const auth = useAuthStore()
const expanded = ref(false)
const peopleEditor = ref<{ title: string; roles: Participant['role'][] } | null>(null)
const assignAfterConfirm = ref<number | null>(null)
const workflowDialogClosed = ref(true)
const bodyId = useId()
const flow = ref<Workflow | null>(null)
const people = ref<Participants['participants']>([])
const failed = ref(false)
const busy = ref(false)
const reason = ref('')
const reasonError = ref(false)
const submitError = ref('')
const pending = ref<WorkflowAction['action'] | null>(null)
const steps = ['DRAFT', 'CONFIRMED', 'DEVELOPING', 'TESTING', 'DONE', 'ONLINE']
const roles = ['CONFIRM', 'DEVELOP', 'DEVELOP', 'ACCEPT', '', '']
const designLabels = { NOT_REQUIRED: '不需要设计', PENDING: '未开始', IN_PROGRESS: '进行中', DONE: '已完成' }
const actionLabels: Record<string, string> = { REOPEN: '重新打开需求', CONFIRM: '确认当前内容', REQUEST_CHANGES: '要求补充说明', DESIGN_PENDING: '启用 / 重新打开设计', DESIGN_START: '开始设计', DESIGN_DONE: '完成设计', DESIGN_CANCEL: '取消设计要求', LEGACY_MIGRATION: '历史数据迁入（未补造确认）' }
const identity = computed(() => `${auth.user?.id}:${auth.accessToken}:${auth.permissionCodes.join(',')}`)
watch([() => props.item.id, identity], () => { expanded.value = false; peopleEditor.value = null; assignAfterConfirm.value = null }, { flush: 'sync' })
let sequence = 0
async function load() {
  const request = ++sequence
  flow.value = null; people.value = []; failed.value = false; pending.value = null; submitError.value = ''
  if (!auth.hasPermission('rd.requirement.view')) return
  try {
    const [workflow, participants] = await Promise.all([getWorkflow(props.item.id), getParticipants(props.item.id)])
    if (request !== sequence) return
    if (!Array.isArray(workflow.records) || !Array.isArray(participants.participants)) throw new Error('Invalid workflow response')
    flow.value = workflow; people.value = participants.participants
  } catch { if (request === sequence) failed.value = true }
}
watch(() => [props.item.id, props.item.revision, identity.value], load, { immediate: true, flush: 'sync' })
onScopeDispose(() => { sequence++ })
const current = computed(() => steps.indexOf(props.item.status === 'PAUSED' ? flow.value?.paused_from || '' : props.item.status))
const canAct = computed(() => !props.readonly && auth.hasPermission('rd.requirement.status') && !['ONLINE', 'CANCELED'].includes(props.item.status))
const canReopen = computed(() => !props.readonly && auth.hasPermission('rd.requirement.status') && props.item.status === 'CANCELED')
const canEditPeople = computed(() => !props.readonly && auth.hasPermission('rd.requirement.edit') && auth.hasPermission('rd.requirement.view') && !['ONLINE', 'CANCELED'].includes(props.item.status))
watch(canEditPeople, allowed => { if (!allowed) { peopleEditor.value = null; assignAfterConfirm.value = null } }, { flush: 'sync' })
watch(() => [props.item.status, props.item.revision, assignAfterConfirm.value, workflowDialogClosed.value], () => {
  if (!workflowDialogClosed.value || assignAfterConfirm.value === null || props.item.revision <= assignAfterConfirm.value) return
  assignAfterConfirm.value = null
  if (props.item.status === 'CONFIRMED') editPeople('CONFIRMED')
}, { flush: 'post' })
function editPeople(step: string) {
  if (!canEditPeople.value) return
  peopleEditor.value = step === 'DRAFT'
    ? { title: '选择需求确认人', roles: ['CONFIRM'] }
    : step === 'TESTING'
      ? { title: '调整验收人员', roles: ['ACCEPT'] }
      : { title: '安排设计、开发与验收人员', roles: ['DESIGN', 'DEVELOP', 'ACCEPT'] }
}
const hasRole = (role: string) => people.value.some(p => p.role === role && p.active)
const isRole = (role: string) => people.value.some(p => p.role === role && p.active && p.user_id === auth.user?.id)
const canRole = (role: string) => hasRole(role) && (isRole(role) || !!auth.user?.can_view_api_docs)
const actionRole = (action: WorkflowAction['action']) => ['CONFIRM', 'REQUEST_CHANGES'].includes(action) ? 'CONFIRM' : 'DESIGN'
const delegated = computed(() => !!pending.value && pending.value !== 'REOPEN' && !isRole(actionRole(pending.value)))
const reasonRequired = computed(() => delegated.value || pending.value === 'REOPEN' || pending.value === 'REQUEST_CHANGES' || pending.value === 'DESIGN_CANCEL' || (pending.value === 'DESIGN_PENDING' && flow.value?.design_status === 'DONE'))
const reasonLabel = computed(() => delegated.value ? '代操作原因（必填）' : pending.value === 'REQUEST_CHANGES' ? '补充说明意见（必填）' : reasonRequired.value ? '说明（必填）' : '说明（选填）')
const names = (role: string) => people.value.filter(p => p.role === role).map(p => p.display_name + (p.active ? '' : '（已停用）')).join('、') || '待分配'
const summaryDetail = computed(() => {
  if (failed.value) return '进度加载失败，展开重试'
  if (!flow.value) return '正在加载进度…'
  if (props.item.status === 'CANCELED') return '流程已取消'
  if (props.item.status === 'ONLINE') return '版本已实际发布'
  const role = roles[current.value]
  const detail = role ? names(role) : props.item.current_version_id ? `所属版本 #${props.item.current_version_id}` : '尚未关联版本'
  return props.item.status === 'PAUSED' && flow.value.paused_from
    ? `暂停前：${requirementStatusLabel[flow.value.paused_from]} · ${detail}`
    : detail
})
const statusRole = (target: string) => target === 'DEVELOPING' ? (props.item.status === 'TESTING' ? 'ACCEPT' : 'DEVELOP') : target === 'TESTING' ? 'DEVELOP' : target === 'DONE' ? 'ACCEPT' : null
const actions = computed(() => availableRequirementStatusActions(props.item.status, canAct.value).filter(a => {
  if (a.target === 'CONFIRMED' && props.item.status === 'DRAFT') return false
  if (a.target === 'DEVELOPING') return canRole(props.item.status === 'TESTING' ? 'ACCEPT' : 'DEVELOP')
  if (a.target === 'TESTING') return canRole('DEVELOP')
  if (a.target === 'DONE') return canRole('ACCEPT')
  return true
}).map(action => {
  const role = statusRole(action.target)
  return role && !isRole(role)
    ? { ...action, needsReason: true, reasonLabel: '代操作原因（必填）' }
    : action
}))
const primaryAction = computed(() => {
  const target = ({ CONFIRMED: 'DEVELOPING', DEVELOPING: 'TESTING', TESTING: 'DONE', DONE: 'DEVELOPING', PAUSED: 'DEVELOPING' } as Record<string, string>)[props.item.status]
  return actions.value.find(action => action.target === target)
})
const otherActions = computed(() => actions.value.filter(action => action !== primaryAction.value))
const roleLabels: Record<string, string> = { CONFIRM: '需求确认人', DEVELOP: '开发人员', ACCEPT: '验收人员', DESIGN: '设计人员' }
const missingRoles = computed(() => {
  if (!flow.value || !canAct.value) return []
  const required: string[] = []
  if (flow.value.needs_confirmation) required.push('CONFIRM')
  if (['CONFIRMED', 'DEVELOPING', 'DONE', 'PAUSED'].includes(props.item.status)) required.push('DEVELOP')
  if (['DEVELOPING', 'TESTING'].includes(props.item.status)) required.push('ACCEPT')
  if (['CONFIRMED', 'DEVELOPING'].includes(props.item.status) && ['PENDING', 'IN_PROGRESS'].includes(flow.value.design_status)) required.push('DESIGN')
  return required.filter(role => !hasRole(role))
})
function assignRole(role: string) {
  if (canEditPeople.value) peopleEditor.value = { title: `设置${roleLabels[role]}`, roles: [role as Participant['role']] }
}
function statusBlocked(action: ReqStatusAction) {
  if (!flow.value) return true
  if (['DEVELOPING', 'TESTING', 'DONE'].includes(action.target) && flow.value.needs_confirmation) return true
  return action.target === 'TESTING' && (!hasRole('ACCEPT') || !['NOT_REQUIRED', 'DONE'].includes(flow.value.design_status))
}
function beginStatus(action: ReqStatusAction) {
  if (canAct.value && !statusBlocked(action)) emit('status', action)
}
const designActions = computed<WorkflowAction['action'][]>(() => {
  if (!flow.value || !canAct.value || !canRole('DESIGN') || !['CONFIRMED', 'DEVELOPING'].includes(props.item.status)) return []
  return ({ NOT_REQUIRED: ['DESIGN_PENDING'], PENDING: ['DESIGN_START', 'DESIGN_CANCEL'], IN_PROGRESS: ['DESIGN_DONE', 'DESIGN_CANCEL'], DONE: ['DESIGN_PENDING', 'DESIGN_CANCEL'] } as Record<string, WorkflowAction['action'][]>)[flow.value.design_status] || []
})
function canWorkflow(action: WorkflowAction['action']) {
  return action === 'REOPEN' ? canReopen.value : canAct.value && canRole(actionRole(action))
}
function begin(action: WorkflowAction['action']) {
  if (!canWorkflow(action)) return
  workflowDialogClosed.value = false
  pending.value = action; reason.value = ''; reasonError.value = false; submitError.value = ''
}
async function submit() {
  if (!flow.value || !pending.value || busy.value || !canWorkflow(pending.value)) return
  reasonError.value = reasonRequired.value && !reason.value.trim()
  if (reasonError.value) return
  const id = props.item.id
  const actor = identity.value
  const shouldAssign = pending.value === 'CONFIRM' && props.item.status === 'DRAFT' && canEditPeople.value
  const revision = flow.value.revision
  busy.value = true; submitError.value = ''
  try {
    await actWorkflow(id, { action: pending.value, revision, reason: reason.value.trim() || null })
    if (id !== props.item.id || actor !== identity.value) return
    pending.value = null
    if (shouldAssign && canEditPeople.value) assignAfterConfirm.value = revision
    emit('updated')
  }
  catch (error) { if (id === props.item.id && actor === identity.value) submitError.value = actionErrorMessage(error) }
  finally { busy.value = false }
}
function recordLabel(action: string) { return actionLabels[action] || requirementStatusLabel[action.replace('STATUS_', '')] || action }
</script>
<template>
  <SectionCard class="requirement-progress" :padded="false">
    <button class="progress-toggle" type="button" :aria-expanded="expanded" :aria-controls="bodyId" :aria-label="expanded ? '收起需求进度' : '展开需求进度'" @click="expanded = !expanded">
      <span class="progress-title">需求进度</span>
      <span class="progress-status">{{ requirementStatusLabel[item.status] }}</span>
      <span class="progress-summary" :title="summaryDetail">{{ summaryDetail }}</span>
      <span v-if="flow?.needs_confirmation" class="progress-notice">内容待确认</span>
      <span class="progress-toggle-label">{{ expanded ? '收起' : '展开' }}<span class="progress-chevron" :class="{ expanded }" aria-hidden="true">⌄</span></span>
    </button>
    <div v-if="flow && (canAct || canReopen)" class="progress-actions" aria-label="当前进度操作">
      <div v-for="role in missingRoles" :key="role" class="progress-blocker" role="status">
        <span>尚未设置有效的{{ roleLabels[role] }}；{{ canEditPeople ? '请先设置后再执行对应流程操作。' : '请联系有人员编辑权限的成员完成设置。' }}</span>
        <el-button v-if="canEditPeople" link type="primary" @click="assignRole(role)">设置{{ roleLabels[role] }}</el-button>
      </div>
      <p v-if="canAct && item.status === 'DEVELOPING' && !['NOT_REQUIRED', 'DONE'].includes(flow.design_status)" class="progress-blocker" role="status">设计尚未完成，暂不能提交验收。请由设计人员完成设计，或填写原因取消设计要求。</p>
      <el-button v-if="canReopen" type="primary" @click="begin('REOPEN')">重新打开需求</el-button>
      <el-button v-if="canAct && flow.needs_confirmation && canRole('CONFIRM')" type="primary" @click="begin('CONFIRM')">确认当前内容</el-button>
      <el-button v-if="primaryAction" :type="flow.needs_confirmation ? 'default' : 'primary'" :disabled="statusBlocked(primaryAction)" @click="beginStatus(primaryAction)">{{ primaryAction.label }}</el-button>
      <details v-if="otherActions.length || designActions.length || (canAct && item.status === 'DRAFT' && canRole('CONFIRM'))" class="progress-more" :open="expanded">
        <summary>更多操作</summary>
        <div class="progress-secondary">
          <el-button v-if="canAct && item.status === 'DRAFT' && canRole('CONFIRM')" @click="begin('REQUEST_CHANGES')">要求补充说明</el-button>
          <el-button v-for="action in otherActions" :key="action.target" :disabled="statusBlocked(action)" @click="beginStatus(action)">{{ action.label }}</el-button>
          <el-button v-for="action in designActions" :key="action" @click="begin(action)">{{ actionLabels[action] }}</el-button>
        </div>
      </details>
    </div>
    <div v-show="expanded" :id="bodyId" class="progress-body">
    <template v-if="expanded">
    <p v-if="failed">进度加载失败 <el-button link @click="load">重试</el-button></p>
    <template v-else-if="flow">
      <el-alert v-if="item.status === 'PAUSED' || item.status === 'CANCELED'" :title="`${requirementStatusLabel[item.status]}${flow.paused_from ? ' · 暂停前：' + requirementStatusLabel[flow.paused_from] : ''}`" type="warning" :closable="false" />
      <el-alert v-if="flow.needs_confirmation" :title="!hasRole('CONFIRM') ? (canEditPeople ? '请先在待确认卡片设置有效的需求确认人，再确认当前内容。' : '尚未设置有效的需求确认人，请联系有人员编辑权限的成员完成设置。') : '当前内容待确认；修改范围或验收标准后，需要重新确认才能继续流转。'" type="warning" :closable="false" />
      <p v-if="flow.legacy_completed">历史完成记录：保留原发布资格，不补造人员确认。</p>
      <ol class="progress-steps" aria-label="需求阶段">
        <li v-for="(step, index) in steps" :key="step" :class="{ current: current === index, completed: current > index }" :aria-current="current === index ? 'step' : undefined">
          <span class="step-dot" aria-hidden="true">{{ current > index ? '✓' : current === index ? '●' : index + 1 }}</span>
          <div><strong>{{ requirementStatusLabel[step] }}</strong><small>{{ current === index ? (item.status === 'PAUSED' ? '暂停于此' : '当前阶段') : current > index ? '已流转' : '尚未到达' }}</small>
            <template v-if="step === 'CONFIRMED'">
              <p>开发：{{ names('DEVELOP') }}</p>
              <p>设计：{{ names('DESIGN') }}</p>
              <p>验收：{{ names('ACCEPT') }}</p>
            </template>
            <p v-else-if="roles[index]">{{ step === 'DRAFT' ? '确认：' : step === 'TESTING' ? '验收：' : '开发：' }}{{ names(roles[index]!) }}</p>
            <p v-if="step === 'DRAFT'">{{ flow.needs_confirmation ? '等待确认当前内容' : flow.records.some(r => r.action === 'CONFIRM' || r.action === 'STATUS_CONFIRMED') ? '当前内容已确认' : '历史阶段兼容，未补造确认' }}</p>
            <small v-if="step === 'TESTING'">任意一名验收人通过即可</small>
            <p v-if="step === 'DEVELOPING'">设计：{{ designLabels[flow.design_status] }} · {{ names('DESIGN') }}</p>
            <p v-if="step === 'DONE'">{{ item.current_version_id ? `所属版本 #${item.current_version_id}` : '尚未关联版本，无法发布' }}</p>
            <p v-if="step === 'ONLINE'">{{ item.status === 'ONLINE' ? '版本已实际发布' : '等待版本实际发布' }}</p>
            <el-button v-if="canEditPeople && step === 'DRAFT'" class="step-people-button" size="small" @click="editPeople(step)">{{ hasRole('CONFIRM') ? '调整确认人' : '设置确认人' }}</el-button>
            <el-button v-if="canEditPeople && step === 'CONFIRMED' && current >= 1" class="step-people-button" size="small" @click="editPeople(step)">选择 / 调整人员</el-button>
            <small v-if="step === 'CONFIRMED' && current === 0">{{ canEditPeople ? '需求确认后将弹窗安排人员' : '需求确认后，由有编辑权限的成员安排人员' }}</small>
            <el-button v-if="canEditPeople && step === 'TESTING' && current >= 3" class="step-people-button" size="small" @click="editPeople(step)">调整验收人</el-button>
          </div>
        </li>
      </ol>
      <details class="progress-history"><summary>查看流转与确认记录（最近 {{ flow.records.length }} 条）</summary>
        <p v-if="!flow.records.length">尚无确认或流转记录。</p>
        <article v-for="record in flow.records" :key="record.id"><strong>{{ recordLabel(record.action) }}</strong> · {{ record.actor_id ? `${record.detail.actor_name || '实际操作人'} #${record.actor_id}` : '历史迁移' }} · {{ formatLocalDateTime(record.created_at) }}<p v-if="record.detail.reason">{{ record.detail.reason }}</p><details v-if="record.detail.description"><summary>当时确认的内容</summary><RichTextContent :content="typeof record.detail.description === 'string' ? record.detail.description : ''" :format="record.detail.description_format === 'HTML' ? 'HTML' : 'PLAIN'" /><p class="multiline">{{ record.detail.acceptance_criteria }}</p></details></article>
      </details>
    </template>
    <p v-else>正在加载进度…</p>
    </template>
    </div>
    <RequirementPeopleDialog v-if="peopleEditor && canEditPeople" :id="item.id" :roles="peopleEditor.roles" :title="peopleEditor.title" @close="peopleEditor = null" @updated="emit('updated')" />
    <el-dialog :model-value="pending !== null" :title="pending ? actionLabels[pending] : ''" width="min(520px, calc(100vw - 24px))" append-to-body @close="pending = null" @closed="workflowDialogClosed = true">
      <el-form label-position="top" @submit.prevent="submit"><el-form-item :label="reasonLabel" :required="reasonRequired" :error="reasonError ? '请填写说明后再提交' : undefined"><el-input v-model="reason" type="textarea" maxlength="500" @input="reasonError = false" /></el-form-item><p v-if="submitError" role="alert">{{ submitError }}</p><el-button type="primary" native-type="submit" :loading="busy">确认操作</el-button></el-form>
    </el-dialog>
  </SectionCard>
</template>
<style scoped>
.requirement-progress { margin-bottom: var(--if-space-4); }
.progress-blocker { flex-basis: 100%; margin: 0; color: var(--el-color-warning-dark-2); font-size: 13px; line-height: 1.7; }
.step-people-button { margin-top: 8px; max-width: 100%; min-height: 32px; padding-inline: 8px; white-space: nowrap; }
.progress-toggle { width: 100%; min-height: 56px; display: flex; align-items: center; gap: 12px; padding: 12px var(--if-space-5); border: 0; border-radius: var(--if-radius); background: transparent; color: var(--if-text-primary); font: inherit; font-size: 13px; text-align: left; cursor: pointer; }
.progress-toggle:hover { background: var(--if-bg-muted); }
.progress-toggle:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: 2px; }
.progress-title { flex-shrink: 0; font-size: 14px; font-weight: 600; }
.progress-status { flex-shrink: 0; padding: 3px 8px; border-radius: 4px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-size: 12px; }
.progress-summary { flex: 1; min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; color: var(--if-text-3); }
.progress-notice { flex-shrink: 0; color: var(--el-color-warning-dark-2); font-size: 12px; }
.progress-toggle-label { flex-shrink: 0; display: flex; align-items: center; gap: 6px; margin-left: auto; color: var(--el-color-primary); }
.progress-chevron { display: inline-block; font-size: 18px; line-height: 1; }.progress-chevron.expanded { transform: rotate(180deg); }
.progress-body { container: requirement-progress / inline-size; border-top: 1px solid var(--if-border); padding: var(--if-space-4) var(--if-space-5); }
.progress-steps { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; list-style: none; padding: 16px 0; margin: 0; }
.progress-steps li { min-width: 0; padding: 12px; border: 1px solid var(--if-border); border-radius: 8px; font-size: 12px; }
.progress-steps li.current { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.step-dot { width: 24px; height: 24px; margin-bottom: 8px; border-radius: 50%; display: grid; place-items: center; background: var(--if-bg-muted, #eee); }
.current .step-dot { background: var(--el-color-primary); color: white; }.completed .step-dot { background: var(--el-color-success-light-8); color: var(--el-color-success-dark-2); }
small { display: block; margin-top: 4px; color: var(--if-text-3); }p { margin: 8px 0; overflow-wrap: anywhere; }.progress-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 0 var(--if-space-5) var(--if-space-4); }.progress-more summary { padding: 8px; color: var(--el-color-primary); }.progress-secondary { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }.progress-more[open] { flex-basis: 100%; }.progress-actions .el-button { margin: 0; }.progress-history { margin-top: 20px; }.progress-history article { border-top: 1px solid var(--if-border, #eee); padding: 12px 0; }.multiline { white-space: pre-wrap; }summary { cursor: pointer; }
/* Keep each card at least 144px wide, including inside a desktop detail drawer. */
@container requirement-progress (min-width: 300px) { .progress-steps { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@container requirement-progress (min-width: 456px) { .progress-steps { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@container requirement-progress (min-width: 924px) { .progress-steps { grid-template-columns: repeat(6, minmax(0, 1fr)); } }
@media (max-width: 767px) {
  .progress-toggle { display: grid; grid-template-columns: auto auto minmax(0, 1fr) auto; gap: 8px; padding: 12px var(--if-space-4); }
  .progress-toggle-label { grid-column: 4; grid-row: 1; min-height: 24px; }
  .progress-summary { grid-column: 1 / -1; grid-row: 2; }
  .progress-notice { grid-column: 3; grid-row: 1; min-width: 0; font-size: 11px; }
  .progress-actions { padding-inline: var(--if-space-4); }.progress-actions .el-button, .progress-more summary { min-height: 44px; }
  .progress-body { padding: var(--if-space-4); }
  .progress-steps { gap: 8px; }
}
</style>
