<script setup lang="ts">
import { computed, nextTick, onScopeDispose, ref, useId, watch } from 'vue'
import { batchActions, submitVersionAcceptance, type ActionKind, type BatchActionResult, type BatchPayload } from '@/api/entityActions'
import { getRequirement } from '@/api/requirements'
import { getFeedback } from '@/api/feedbacks'
import { getVersion } from '@/api/versions'
import { getWorkflow, getParticipants, getFeedbackCollaboration } from '@/api/collaboration'
import { useAuthStore } from '@/stores/auth'
import { useResponsive } from '@/composables/useResponsive'
import { feedbackStatusLabel } from '@/constants/feedback'
import { requirementStatusLabel } from '@/constants/requirement'
import { actionErrorMessage } from '@/utils/actionError'
import RequirementPeopleDialog from './RequirementPeopleDialog.vue'

type BatchRow = { id: number; title: string; requirement_no?: string; feedback_no?: string; status?: string }
const props = withDefaults(defineProps<{ kind: ActionKind; rows: BatchRow[]; scope?: 'current-page' | 'version-list'; versionId?: number; versionRevision?: number }>(), { scope: 'current-page' })
const emit = defineEmits<{ updated: [] }>()
const auth = useAuthStore()
const { isMobile } = useResponsive()
const actionGroup = useId()
const open = ref(false)
const sessionKind = ref<ActionKind>(props.kind)
const sessionScope = ref(props.scope)
const sessionVersionId = ref(props.versionId)
const kind = computed(() => open.value ? sessionKind.value : props.kind)
const versionScope = computed(() => (open.value ? sessionScope.value : props.scope) === 'version-list')
const versionSubmission = computed(() => kind.value === 'requirements' && versionScope.value && action.value === 'SUBMIT_ACCEPTANCE')
const checkedVersion = ref<{ id: number; revision: number; system_id: number | null } | null>(null)
const peopleEditor = ref<number | null>(null)
const locked = computed(() => busy.value || peopleEditor.value !== null)
const canEditPeople = computed(() => auth.hasPermission('rd.requirement.view') && auth.hasPermission('rd.requirement.edit'))
const selected = ref<number[]>([])
const action = ref('')
const reason = ref('')
const busy = ref(false)
const submitting = ref(false)
const error = ref('')
const reasonValidationRequested = ref(false)
const stage = ref<'select' | 'review' | 'result'>('select')
const heading = ref<HTMLElement>()
const body = ref<HTMLElement>()
type Preview = { id: number; title: string; code: string; status: string; revision: number; blocker: string; delegated: boolean; shortcut?: boolean; missingPeople?: boolean }
const preview = ref<Preview[]>([])
const results = ref<BatchActionResult[]>([])
const entity = computed(() => kind.value === 'requirements' ? '需求' : '反馈')
const dialogTitle = computed(() => `批量处理${entity.value}`)
const scopeLabel = computed(() => versionScope.value ? '当前版本清单的筛选结果' : '当前页')
const options = computed(() => kind.value === 'requirements'
  ? [
      { value: 'CONFIRM', label: '确认需求', transition: '待确认 → 待开发', description: '由需求确认人确认当前内容；其他阶段仅重新确认内容，保留原阶段。' },
      { value: 'DEVELOPING', label: '开始开发', transition: '待开发 → 开发中', description: '由开发人员开始处理已确认的需求。' },
      versionScope.value
        ? { value: 'SUBMIT_ACCEPTANCE', label: '提交验收', transition: '待开发 / 开发中 → 待验收', description: '已完成开发的需求可直接提交；待开发需求省去开始开发登记，仍由验收人确认。' }
        : { value: 'TESTING', label: '提交验收', transition: '开发中 → 待验收', description: '由开发人员提交；内容已确认、设计已完成或无需设计，并已指定验收人。' },
      { value: 'DONE', label: '验收通过', transition: '待验收 → 待发布', description: '由任一有效验收人确认通过；之后仍需在版本中发布。' },
    ]
  : [
      { value: 'ACCEPTED', label: '受理反馈', transition: '待处理 → 已受理', description: '由任一指定接收人受理；没有指定接收人时，由有权限的人员处理。' },
      { value: 'CLOSED', label: '关闭反馈', transition: '待处理 / 已受理 → 已关闭', description: '关闭不再跟进的反馈，需填写关闭原因。' },
    ])
const chosen = computed(() => options.value.find(option => option.value === action.value))
const submitLabel = computed(() => action.value === 'CONFIRM' ? '确认需求' : `确认${chosen.value?.label ?? ''}`)
const permission = computed(() => kind.value === 'requirements' ? 'rd.requirement.status' : 'rd.feedback.edit')
const eligible = computed(() => preview.value.filter(row => !row.blocker))
const skipped = computed(() => preview.value.filter(row => row.blocker))
const hasShortcut = computed(() => eligible.value.some(row => row.shortcut))
const hasDelegation = computed(() => eligible.value.some(row => row.delegated))
const reasonRequired = computed(() => action.value === 'CLOSED' || hasShortcut.value || hasDelegation.value)
const reasonLabel = computed(() => action.value === 'CLOSED' ? '关闭原因' : hasShortcut.value ? hasDelegation.value ? '直接提交及代操作说明' : '直接提交验收说明' : hasDelegation.value ? '代操作原因' : '说明（选填）')
const reasonError = computed(() => reasonValidationRequested.value && stage.value === 'review' && (reasonRequired.value || (versionSubmission.value && reason.value.trim().length > 0)) && reason.value.trim().length < 2 ? `请填写${reasonLabel.value}（至少 2 个字符）` : '')
const reasonHint = computed(() => action.value === 'CLOSED' ? '说明为什么不再跟进，这段原因将用于本次关闭的所有反馈。' : hasShortcut.value ? `请说明开发已完成但未登记开始开发的情况。${hasDelegation.value ? '同时说明代指定开发人员提交的原因；' : ''}本次仅提交验收，仍需验收人员确认通过。` : hasDelegation.value ? '部分记录由你代指定人员操作，请说明代操作原因；将记录本次实际操作者。' : '说明将随本次操作记录保存。')
const resultRows = computed(() => preview.value.map(row => {
  const result = results.value.find(item => item.id === row.id)
  const outcome = row.blocker ? '跳过' : !result ? '待核对' : result.success ? '成功' : '失败'
  return { ...row, outcome, message: row.blocker || result?.message || '尚未取得确定结果，请打开详情核对实际状态。' }
}))
const resultCount = (outcome: string) => resultRows.value.filter(row => row.outcome === outcome).length
const identity = computed(() => `${auth.user?.id}:${auth.accessToken}:${auth.permissionCodes.join(',')}`)
let sequence = 0
watch(identity, () => { sequence++; open.value = false; busy.value = false; submitting.value = false; peopleEditor.value = null; checkedVersion.value = null; preview.value = []; results.value = []; stage.value = 'select' })
watch(() => `${props.kind}:${props.scope}:${props.versionId}:${props.versionRevision}:${props.rows.map(row => row.id).join(',')}`, () => {
  // A refresh after execution must not replace the submitted names or results.
  if (submitting.value || stage.value === 'result') return
  sessionKind.value = props.kind
  sessionScope.value = props.scope; sessionVersionId.value = props.versionId
  sequence++; busy.value = false; peopleEditor.value = null; checkedVersion.value = null; selected.value = []; preview.value = []; stage.value = 'select'
  error.value = open.value ? '列表已变化，请重新选择并检查记录。' : ''
  if (!options.value.some(option => option.value === action.value)) action.value = ''
}, { flush: 'sync' })
watch([selected, action], () => { sequence++; busy.value = false; checkedVersion.value = null; preview.value = []; results.value = []; stage.value = 'select'; error.value = '' }, { deep: true, flush: 'sync' })
onScopeDispose(() => { sequence++ })
function code(row: BatchRow) { return (kind.value === 'requirements' ? row.requirement_no : row.feedback_no) || `#${row.id}` }
function statusLabel(status?: string) { return status ? (kind.value === 'requirements' ? requirementStatusLabel : feedbackStatusLabel)[status] || status : '检查时获取最新状态' }
function detailLink(id: number) { return `#/${kind.value}/${id}` }
function begin() {
  sessionKind.value = props.kind; sessionScope.value = props.scope; sessionVersionId.value = props.versionId
  peopleEditor.value = null; checkedVersion.value = null
  selected.value = []; action.value = ''; reason.value = ''; error.value = ''; reasonValidationRequested.value = false; preview.value = []; results.value = []; stage.value = 'select'; open.value = true
}
function close() { if (!locked.value) { sequence++; open.value = false } }
function selectPage() { if (!busy.value) selected.value = props.rows.slice(0, 50).map(row => row.id) }
async function focusHeading() { await nextTick(); if (body.value) body.value.scrollTop = 0; heading.value?.focus({ preventScroll: true }) }
function back() { if (!locked.value) { sequence++; checkedVersion.value = null; preview.value = []; stage.value = 'select'; error.value = ''; void focusHeading() } }
function arrangePeople(row: Preview) {
  if (locked.value || !versionSubmission.value || !row.missingPeople || !canEditPeople.value) return
  peopleEditor.value = row.id
}
async function peopleUpdated() {
  peopleEditor.value = null
  await check()
}
function peopleClosed() { peopleEditor.value = null; if (!busy.value) void focusHeading() }
async function inspect(id: number): Promise<Preview> {
  const original = props.rows.find(row => row.id === id)!
  const base = { id, title: original.title, code: code(original), status: statusLabel(original.status) }
  try {
    if (kind.value === 'feedbacks') {
      const [item, people] = await Promise.all([getFeedback(id), getFeedbackCollaboration(id)])
      const allowed = action.value === 'ACCEPTED' ? item.status === 'NEW' : ['NEW', 'ACCEPTED'].includes(item.status)
      let blocker = allowed ? '' : `当前为「${statusLabel(item.status)}」，${action.value === 'ACCEPTED' ? '仅待处理反馈可受理' : '仅待处理或已受理反馈可关闭'}。`
      const delegated = action.value === 'ACCEPTED' && people.recipients.length > 0 && !people.recipients.some(p => p.id === auth.user?.id)
      if (!blocker && delegated && !auth.user?.can_view_api_docs) blocker = '请由指定接收人受理；可在反馈详情查看接收人。'
      if (people.revision !== item.revision) blocker = '信息已变化，请返回调整后重新检查。'
      return { ...base, title: item.title || base.title, code: item.feedback_no || base.code, status: statusLabel(item.status), revision: item.revision, blocker, delegated }
    }
    const [item, workflow, people] = await Promise.all([getRequirement(id), getWorkflow(id), getParticipants(id)])
    const source: Record<string, string[]> = { CONFIRM: ['DRAFT', 'CONFIRMED', 'DEVELOPING', 'TESTING', 'DONE', 'PAUSED'], DEVELOPING: ['CONFIRMED'], TESTING: ['DEVELOPING'], SUBMIT_ACCEPTANCE: ['CONFIRMED', 'DEVELOPING'], DONE: ['TESTING'] }
    const sourceHint: Record<string, string> = { CONFIRM: '已上线或已取消的需求不能确认内容', DEVELOPING: '仅待开发需求可开始开发', TESTING: '仅开发中需求可提交验收', SUBMIT_ACCEPTANCE: '仅待开发或开发中需求可提交验收', DONE: '仅待验收需求可验收通过' }
    let blocker = source[action.value]?.includes(item.status) ? '' : `当前为「${statusLabel(item.status)}」，${sourceHint[action.value]}。`
    if (versionSubmission.value && item.current_version_id !== sessionVersionId.value) blocker = '需求已不在当前版本中，请刷新版本清单后重新选择。'
    if (versionSubmission.value && !blocker && (!checkedVersion.value?.system_id || !item.system_id || checkedVersion.value.system_id !== item.system_id)) blocker = '需求或版本未指定业务系统，或双方系统不一致；请先在详情中处理。'
    const role = action.value === 'CONFIRM' ? 'CONFIRM' : action.value === 'DONE' ? 'ACCEPT' : 'DEVELOP'
    const roleName = { CONFIRM: '需求确认人', ACCEPT: '验收人员', DEVELOP: '开发人员' }[role]
    const members = people.participants.filter(p => p.role === role && p.active)
    const delegated = members.length > 0 && !members.some(p => p.user_id === auth.user?.id)
    const submittingAcceptance = action.value === 'TESTING' || versionSubmission.value
    const missingRoles = (['DEVELOP', 'ACCEPT'] as const).filter(r => !people.participants.some(p => p.role === r && p.active))
    const missingPeople = versionSubmission.value && !blocker && missingRoles.length > 0
    if (missingPeople) blocker = `尚未设置有效${missingRoles.map(r => r === 'DEVELOP' ? '开发人员' : '验收人员').join('、')}，请先设置人员后重新检查。`
    if (!blocker && !members.length) blocker = `尚未设置有效${roleName}，请到需求详情的进度区域设置。`
    if (!blocker && delegated && !auth.user?.can_view_api_docs) blocker = `请由指定的${roleName}执行，可在需求详情查看人员。`
    if (!blocker && action.value === 'CONFIRM' && !workflow.needs_confirmation) blocker = '当前内容已确认，无需重复确认。'
    if (!blocker && action.value !== 'CONFIRM' && workflow.needs_confirmation) blocker = '当前内容需要重新确认，请先由需求确认人确认后再处理。'
    if (!blocker && submittingAcceptance && !people.participants.some(p => p.role === 'ACCEPT' && p.active)) blocker = '尚未设置有效验收人员，请到需求详情的进度区域设置。'
    if (!blocker && submittingAcceptance && !['NOT_REQUIRED', 'DONE'].includes(workflow.design_status)) blocker = '设计尚未完成，请先在需求详情完成设计或说明无需设计的原因。'
    if (item.revision !== workflow.revision || item.revision !== people.revision) blocker = '信息已变化，请返回调整后重新检查。'
    return { ...base, title: item.title || base.title, code: item.requirement_no || base.code, status: statusLabel(item.status), revision: item.revision, blocker, delegated,
      shortcut: versionSubmission.value && item.status === 'CONFIRMED',
      missingPeople: missingPeople && item.revision === workflow.revision && item.revision === people.revision }
  } catch (e) { return { ...base, revision: 0, blocker: `${actionErrorMessage(e)} 请打开详情核对，或返回调整后重新检查。`, delegated: false } }
}
async function check() {
  if (locked.value || !chosen.value || !selected.value.length || selected.value.length > 50 || !auth.hasPermission(permission.value)) return
  const ids = [...selected.value]
  if (ids.some(id => !props.rows.some(row => row.id === id))) return
  const request = ++sequence
  busy.value = true; error.value = ''; reasonValidationRequested.value = false; results.value = []; preview.value = []; checkedVersion.value = null
  if (versionSubmission.value) {
    if (!sessionVersionId.value || !auth.hasPermission('rd.version.view') || !auth.hasPermission('rd.requirement.view')) {
      busy.value = false; error.value = '无法确认当前版本或查看权限，请关闭窗口并刷新版本清单。'; return
    }
    try {
      const version = await getVersion(sessionVersionId.value)
      if (request !== sequence) return
      if (version.id !== sessionVersionId.value || !Number.isInteger(version.revision) || version.revision < 1) throw new Error('Invalid version response')
      if (version.release_frozen || ['RELEASED', 'CANCELED'].includes(version.status)) {
        busy.value = false; error.value = '当前版本已发布或已取消，不能集中提交验收。请关闭窗口刷新版本清单。'; return
      }
      checkedVersion.value = { id: version.id, revision: version.revision, system_id: version.system_id }
    } catch (e) {
      if (request === sequence) { busy.value = false; error.value = `${actionErrorMessage(e)} 请刷新版本清单后重新检查。` }
      return
    }
  }
  const rows: Preview[] = []
  for (let i = 0; i < ids.length; i += 5) {
    const part = await Promise.all(ids.slice(i, i + 5).map(inspect))
    if (request !== sequence) return
    rows.push(...part)
  }
  if (request === sequence) { preview.value = rows; busy.value = false; stage.value = 'review'; void focusHeading() }
}
async function submit() {
  if (locked.value || stage.value !== 'review' || !eligible.value.length || !auth.hasPermission(permission.value)) return
  if (versionSubmission.value && (!checkedVersion.value || !auth.hasPermission('rd.version.view') || !auth.hasPermission('rd.requirement.view'))) return
  reasonValidationRequested.value = true
  if (reasonError.value) return
  const request = ++sequence
  busy.value = true; submitting.value = true; error.value = ''
  try {
    const payload = { action: action.value, items: eligible.value.map(({ id, revision }) => ({ id, revision })), reason: reason.value.trim() || null } as BatchPayload
    const response = versionSubmission.value && checkedVersion.value
      ? await submitVersionAcceptance(checkedVersion.value.id, { version_revision: checkedVersion.value.revision, items: payload.items, reason: payload.reason })
      : await batchActions(kind.value, payload)
    if (request !== sequence) return
    results.value = response.results
    stage.value = 'result'
    emit('updated')
  } catch (e) {
    if (request === sequence) {
      const response = (e as { response?: { status?: number; data?: { message?: unknown } } })?.response
      const message = [403, 409, 422].includes(response?.status ?? 0) && typeof response?.data?.message === 'string' ? response.data.message : '未能取得完整处理结果'
      error.value = `${message}。请先核对实际结果，避免重复处理。`
      stage.value = 'result'
      emit('updated')
    }
  } finally { if (request === sequence) { busy.value = false; submitting.value = false; void focusHeading() } }
}
</script>

<template>
  <el-button v-if="auth.hasPermission(permission)" :disabled="!rows.length" @click="begin">{{ dialogTitle }}</el-button>
  <el-dialog :model-value="open" :title="dialogTitle" width="min(780px, calc(100vw - 24px))" :fullscreen="isMobile" append-to-body :close-on-click-modal="false" :close-on-press-escape="!locked" :show-close="!locked" class="batch-dialog" modal-class="batch-overlay" @close="close">
    <ol class="batch-steps" aria-label="批量处理步骤">
      <li v-for="(label, index) in ['选择操作和记录', '核对并执行', '查看结果']" :key="label" :aria-current="stage === ['select', 'review', 'result'][index] ? 'step' : undefined" :class="{ current: stage === ['select', 'review', 'result'][index] }"><span>{{ index + 1 }}</span>{{ label }}</li>
    </ol>
    <div ref="body" class="batch-body" :aria-busy="busy">
      <template v-if="stage === 'select'">
        <h3 ref="heading" tabindex="-1">选择要执行的操作</h3>
        <fieldset class="batch-actions" :disabled="locked">
          <legend class="sr-only">批量操作类型</legend>
          <label v-for="option in options" :key="option.value" class="batch-action" :class="{ selected: action === option.value }">
            <input v-model="action" type="radio" :value="option.value" :name="actionGroup" />
            <span><strong>{{ option.label }}</strong><span class="batch-transition">{{ option.transition }}</span><small>{{ option.description }}</small></span>
          </label>
        </fieldset>
        <div class="batch-selection-heading"><h3>选择{{ entity }}</h3><strong aria-live="polite">已选 {{ selected.length }} / 50 条</strong></div>
        <p class="batch-hint">{{ scopeLabel }}共 {{ rows.length }} 条{{ entity }}，每次最多选择 50 条。{{ versionScope ? '只包含当前筛选下可见的需求。' : '只包含当前页，不包含其他分页。' }}</p>
        <div class="batch-tools"><el-button :disabled="locked || !rows.length" @click="selectPage">{{ rows.length > 50 ? '选择前 50 条' : versionScope ? '选择当前清单' : '选择当前页' }}</el-button><el-button :disabled="locked || !selected.length" @click="selected = []">清空选择</el-button></div>
        <p v-if="!rows.length" class="batch-empty">当前范围没有记录，请关闭弹窗后调整筛选条件。</p>
        <el-checkbox-group v-model="selected" :max="50" :disabled="locked" class="batch-selection" :aria-label="`选择${entity}`">
          <el-checkbox v-for="row in rows" :key="row.id" :value="row.id" :class="{ picked: selected.includes(row.id) }"><span class="batch-row-code">{{ code(row) }}</span><strong>{{ row.title }}</strong><small>{{ statusLabel(row.status) }}</small></el-checkbox>
        </el-checkbox-group>
      </template>
      <template v-else-if="stage === 'review'">
        <h3 ref="heading" tabindex="-1">核对「{{ chosen?.label }}」的处理范围</h3>
        <p class="batch-hint">{{ chosen?.description }}</p>
        <div class="batch-summary" role="status"><span>已选 {{ preview.length }} 条</span><strong>可执行 {{ eligible.length }} 条</strong><span>跳过 {{ skipped.length }} 条</span></div>
        <p v-if="eligible.length" class="batch-hint">确认后仅对下方 {{ eligible.length }} 条可执行{{ entity }}进行「{{ chosen?.label }}」，其余 {{ skipped.length }} 条保持不变。</p>
        <p v-else class="batch-empty">没有可执行的{{ entity }}。请按下方原因处理，或返回调整操作和选择。</p>
        <ul class="batch-records" aria-label="操作前检查">
          <li v-for="row in preview" :key="row.id">
            <div class="batch-record-heading"><span class="batch-badge" :class="row.blocker ? 'skipped' : 'ready'">{{ row.blocker ? '跳过' : '将执行' }}</span><strong>{{ row.code }} · {{ row.title }}</strong></div>
            <p class="batch-hint">当前：{{ row.status }}</p><p>{{ row.blocker || (row.delegated ? '可操作，需填写代操作原因。' : `符合「${chosen?.label}」的操作条件。`) }}</p>
            <p v-if="!row.blocker && row.shortcut" class="batch-hint">将从待开发直接进入待验收，省去开始开发登记；请确认实际开发已完成，验收仍需由验收人员确认。</p>
            <el-button v-if="row.blocker && row.missingPeople && canEditPeople" class="batch-people-button" :disabled="locked" @click="arrangePeople(row)">设置人员</el-button>
            <a v-if="row.blocker" :href="detailLink(row.id)" target="_blank" rel="noopener">查看详情并处理（新标签页）</a>
          </li>
        </ul>
        <el-form v-if="eligible.length" label-position="top" @submit.prevent="submit">
          <el-form-item :label="reasonLabel" :required="reasonRequired"><el-input v-model="reason" :aria-label="reasonLabel" type="textarea" :rows="3" :maxlength="500" :disabled="locked" :placeholder="reasonRequired ? '请填写原因，至少 2 个字符' : '补充本次操作的说明'" /></el-form-item>
          <p class="batch-hint">{{ reasonHint }}</p>
        </el-form>
      </template>
      <template v-else>
        <h3 ref="heading" tabindex="-1">{{ resultCount('待核对') ? '请核对本次处理结果' : '本次处理结果' }} · {{ chosen?.label }}</h3>
        <div class="batch-summary" role="status"><strong>成功 {{ resultCount('成功') }} 条</strong><span>失败 {{ resultCount('失败') }} 条</span><span>跳过 {{ resultCount('跳过') }} 条</span><span v-if="resultCount('待核对')">待核对 {{ resultCount('待核对') }} 条</span></div>
        <p class="batch-hint">成功项已完成，不会再次执行。{{ resultCount('失败') || resultCount('待核对') ? '请打开未完成记录核对最新状态，处理后从列表重新选择；不会自动重试。' : skipped.length ? '跳过项未做修改，可按原因处理后重新选择。' : '可关闭窗口返回列表查看最新状态。' }}</p>
        <ul class="batch-records" aria-label="批量操作结果">
          <li v-for="row in resultRows" :key="row.id">
            <div class="batch-record-heading"><span class="batch-badge" :class="{ ready: row.outcome === '成功', failed: row.outcome === '失败', skipped: row.outcome === '跳过' || row.outcome === '待核对' }">{{ row.outcome }}</span><strong>{{ row.code }} · {{ row.title }}</strong></div>
            <p>{{ row.message }}</p><a v-if="row.outcome !== '成功'" :href="detailLink(row.id)" target="_blank" rel="noopener">查看详情并处理（新标签页）</a>
          </li>
        </ul>
      </template>
      <p v-if="error || reasonError" class="batch-error" role="alert">{{ error || reasonError }}</p>
    </div>
    <template #footer>
      <div class="batch-footer">
        <p v-if="stage === 'select'" class="batch-hint" role="status">{{ busy ? `正在检查所选${entity}，请稍候…` : !chosen ? '请先选择一种操作，再勾选要处理的记录。' : !selected.length ? `请勾选至少一条${entity}，再进入下一步。` : `下一步仅检查所选 ${selected.length} 条${entity}，不会修改数据。` }}</p>
        <p v-else-if="stage === 'review'" class="batch-hint" role="status">{{ busy ? '正在执行，请勿重复提交。' : '每条记录分别处理，执行时仍会检查最新状态。' }}</p>
        <div class="batch-footer-actions" :class="stage">
          <el-button :disabled="locked" @click="close">{{ stage === 'result' ? '完成并关闭' : '取消' }}</el-button>
          <el-button v-if="stage === 'select'" type="primary" :loading="busy" :disabled="locked || !chosen || !selected.length" @click="check">下一步：检查 {{ selected.length }} 条{{ entity }}</el-button>
          <el-button v-if="stage === 'review'" :disabled="locked" @click="back">返回调整</el-button>
          <el-button v-if="stage === 'review' && eligible.length" :type="action === 'CLOSED' ? 'danger' : 'primary'" :loading="busy" :disabled="locked" @click="submit">{{ submitLabel }}（{{ eligible.length }} 条）</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
  <RequirementPeopleDialog v-if="peopleEditor !== null && open" :id="peopleEditor" :roles="['DEVELOP', 'ACCEPT']" title="设置开发与验收人员" @updated="peopleUpdated" @close="peopleClosed" />
</template>

<style scoped>
:global(.batch-dialog .el-dialog__body) { display: flex; flex-direction: column; overflow: hidden; }
.batch-steps { display: flex; flex-shrink: 0; list-style: none; padding: 0; margin: 0 0 24px; gap: 12px; }
.batch-steps li { flex: 1; display: flex; gap: 8px; align-items: center; color: var(--if-text-secondary); font-size: 13px; }
.batch-steps li > span { display: grid; place-items: center; flex: 0 0 26px; width: 26px; height: 26px; border-radius: 50%; background: var(--if-bg-subtle); }
.batch-steps .current { color: var(--if-info-fg); font-weight: 600; }
.batch-steps .current > span { color: var(--if-text-inverse); background: var(--if-brand-500); }
.batch-body { flex: 1 1 auto; min-height: 0; max-height: min(62vh, 650px); overflow-y: auto; padding: 2px 4px; color: var(--if-text-primary); }
h3 { font-size: 16px; margin: 0 0 12px; line-height: 1.5; }
h3:focus-visible { outline: 2px solid var(--if-brand-500); outline-offset: 2px; }
.batch-actions { border: 0; padding: 0; margin: 0 0 24px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.batch-action { display: flex; align-items: flex-start; gap: 10px; padding: 14px; border: 1px solid var(--if-border-strong); border-radius: var(--if-radius); cursor: pointer; }
.batch-action.selected { border-color: var(--if-brand-500); background: var(--if-info-bg); }
.batch-actions:disabled .batch-action { cursor: wait; opacity: .7; }
.batch-action:focus-within { outline: 2px solid var(--if-brand-500); outline-offset: 2px; }
.batch-action input { margin: 4px 0 0; width: 16px; height: 16px; flex-shrink: 0; accent-color: var(--if-brand-500); }
.batch-action strong, .batch-transition, .batch-action small { display: block; }
.batch-transition { color: var(--if-info-fg); margin: 4px 0; font-size: 13px; }
.batch-action small, .batch-hint { color: var(--if-text-secondary); font-size: 13px; line-height: 1.6; }
.batch-hint { margin: 8px 0 12px; }
.batch-selection-heading, .batch-tools { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }
.batch-selection-heading { justify-content: space-between; }
.batch-selection-heading h3 { margin: 0; }
.batch-selection-heading > strong { font-size: 13px; color: var(--if-info-fg); }
.batch-selection { display: flex; flex-direction: column; margin-top: 12px; }
.batch-selection :deep(.el-checkbox) { padding: 12px; margin: 0; height: auto; min-height: 60px; border: 1px solid var(--if-border); border-bottom-width: 0; align-items: flex-start; }
.batch-selection :deep(.el-checkbox:last-child) { border-bottom-width: 1px; }
.batch-selection :deep(.el-checkbox__input) { margin-top: 4px; }
.batch-selection :deep(.el-checkbox__label) { min-width: 0; white-space: normal; overflow-wrap: anywhere; color: var(--if-text-primary); }
.batch-selection .picked { background: var(--if-info-bg); }
.batch-row-code { color: var(--if-text-secondary); margin-right: 8px; font-size: 12px; }
.batch-selection small { display: block; margin-top: 4px; font-size: 12px; color: var(--if-text-secondary); }
.batch-summary { display: flex; flex-wrap: wrap; gap: 12px 24px; padding: 14px 16px; margin-bottom: 12px; border-radius: var(--if-radius); background: var(--if-info-bg); color: var(--if-info-fg); }
.batch-records { list-style: none; padding: 0; margin: 16px 0; }
.batch-records li { padding: 14px 0; border-bottom: 1px solid var(--if-border); overflow-wrap: anywhere; }
.batch-records p { margin: 8px 0; line-height: 1.6; }
.batch-record-heading { display: flex; gap: 10px; align-items: flex-start; }
.batch-record-heading strong { min-width: 0; }
.batch-badge { flex-shrink: 0; padding: 3px 8px; border-radius: var(--if-radius-xs); font-size: 12px; font-weight: 600; }
.batch-badge.ready { background: var(--if-success-bg); color: var(--if-success-fg); }
.batch-badge.skipped { background: var(--if-warning-bg); color: var(--if-warning-fg); }
.batch-badge.failed, .batch-error { color: var(--if-danger-fg); background: var(--if-danger-bg); }
.batch-error, .batch-empty { padding: 12px; border-radius: var(--if-radius); line-height: 1.6; }
.batch-empty { background: var(--if-bg-subtle); }
.batch-records a { display: inline-flex; align-items: center; min-height: 44px; color: var(--if-info-fg); text-decoration: underline; }
.batch-people-button { min-height: 44px; margin-right: 12px; }
.batch-footer { width: 100%; text-align: left; }
.batch-footer-actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 8px; }
.batch-footer-actions :deep(.el-button + .el-button), .batch-tools :deep(.el-button + .el-button) { margin-left: 0; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
@media (max-width: 767px) {
  :global(.batch-overlay .el-overlay-dialog) { padding: 0; }
  :global(.batch-dialog.is-fullscreen) { width: 100vw !important; max-width: 100vw; height: 100dvh; max-height: 100dvh; border: 0; border-radius: 0; padding-bottom: env(safe-area-inset-bottom); }
  :global(.batch-dialog .el-dialog__headerbtn) { width: 44px; height: 44px; top: 4px; right: 8px; }
  .batch-steps { gap: 6px; margin-bottom: 16px; }
  .batch-steps li { flex-direction: column; align-items: center; gap: 6px; font-size: 12px; text-align: center; }
  .batch-actions { grid-template-columns: 1fr; }
  .batch-body { max-height: none; }
  .batch-footer-actions { display: grid; grid-template-columns: auto minmax(0, 1fr); }
  .batch-footer-actions.review { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .batch-footer-actions.review :deep(.el-button:nth-child(3)), .batch-footer-actions.result :deep(.el-button) { grid-column: 1 / -1; }
  .batch-footer-actions :deep(.el-button), .batch-tools :deep(.el-button) { flex: none; min-width: 72px; min-height: 44px; height: auto; white-space: nowrap; padding: 10px 12px; }
}
</style>
