<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { batchActions, type ActionKind, type BatchActionResult, type BatchPayload } from '@/api/entityActions'
import { getRequirement } from '@/api/requirements'
import { getFeedback } from '@/api/feedbacks'
import { getWorkflow, getParticipants, getFeedbackCollaboration } from '@/api/collaboration'
import { useAuthStore } from '@/stores/auth'
import { actionErrorMessage } from '@/utils/actionError'
const props = defineProps<{ kind: ActionKind; rows: { id: number; title: string }[] }>()
const emit = defineEmits<{ updated: [] }>()
const auth = useAuthStore()
const open = ref(false)
const selected = ref<number[]>([])
const action = ref('')
const reason = ref('')
const busy = ref(false)
const error = ref('')
type Preview = { id: number; title: string; revision: number; blocker: string; delegated: boolean }
const preview = ref<Preview[]>([])
const results = ref<BatchActionResult[]>([])
const options = computed(() => props.kind === 'requirements'
  ? [{ value: 'CONFIRM', label: '确认需求' }, { value: 'DEVELOPING', label: '开始开发' }, { value: 'TESTING', label: '提交验收' }, { value: 'DONE', label: '验收通过' }]
  : [{ value: 'ACCEPTED', label: '受理反馈' }, { value: 'CLOSED', label: '关闭反馈' }])
const permission = computed(() => props.kind === 'requirements' ? 'rd.requirement.status' : 'rd.feedback.edit')
const eligible = computed(() => preview.value.filter(row => !row.blocker))
const reasonRequired = computed(() => action.value === 'CLOSED' || eligible.value.some(row => row.delegated))
const identity = computed(() => `${auth.user?.id}:${auth.accessToken}:${auth.permissionCodes.join(',')}`)
let sequence = 0
watch(identity, () => { sequence++; open.value = false; busy.value = false; preview.value = []; results.value = [] })
watch(() => `${props.kind}:${props.rows.map(row => row.id).join(',')}`, () => {
  if (results.value.length) return
  sequence++; busy.value = false; selected.value = []; preview.value = []
  error.value = open.value ? '列表已变化，请重新选择并检查记录。' : ''
  if (!options.value.some(option => option.value === action.value)) action.value = options.value[0]!.value
}, { flush: 'sync' })
watch([selected, action], () => { sequence++; busy.value = false; preview.value = []; results.value = []; error.value = '' }, { deep: true, flush: 'sync' })
onScopeDispose(() => { sequence++ })
function begin() { selected.value = []; action.value = options.value[0]!.value; reason.value = ''; error.value = ''; open.value = true }
function close() { if (!busy.value) { sequence++; open.value = false } }
async function inspect(id: number): Promise<Preview> {
  const title = props.rows.find(row => row.id === id)?.title || `#${id}`
  try {
    if (props.kind === 'feedbacks') {
      const [item, people] = await Promise.all([getFeedback(id), getFeedbackCollaboration(id)])
      const allowed = action.value === 'ACCEPTED' ? item.status === 'NEW' : ['NEW', 'ACCEPTED'].includes(item.status)
      let blocker = allowed ? '' : '当前状态不支持此操作'
      const delegated = action.value === 'ACCEPTED' && people.recipients.length > 0 && !people.recipients.some(p => p.id === auth.user?.id)
      if (delegated && !auth.user?.can_view_api_docs) blocker = '请由指定接收人受理'
      if (people.revision !== item.revision) blocker = '信息已变化，请重新检查'
      return { id, title, revision: item.revision, blocker, delegated }
    }
    const [item, workflow, people] = await Promise.all([getRequirement(id), getWorkflow(id), getParticipants(id)])
    const source: Record<string, string[]> = { CONFIRM: ['DRAFT', 'CONFIRMED', 'DEVELOPING', 'TESTING', 'DONE', 'PAUSED'], DEVELOPING: ['CONFIRMED'], TESTING: ['DEVELOPING'], DONE: ['TESTING'] }
    let blocker = source[action.value]?.includes(item.status) ? '' : '当前阶段不支持此操作'
    const role = action.value === 'CONFIRM' ? 'CONFIRM' : action.value === 'DONE' ? 'ACCEPT' : 'DEVELOP'
    const members = people.participants.filter(p => p.role === role && p.active)
    const delegated = members.length > 0 && !members.some(p => p.user_id === auth.user?.id)
    if (!blocker && !members.length) blocker = '尚未设置有效的对应环节人员'
    if (!blocker && delegated && !auth.user?.can_view_api_docs) blocker = '仅对应环节人员可操作'
    if (!blocker && action.value === 'CONFIRM' && !workflow.needs_confirmation) blocker = '当前内容已确认'
    if (!blocker && action.value !== 'CONFIRM' && workflow.needs_confirmation) blocker = '当前内容需要重新确认'
    if (!blocker && action.value === 'TESTING' && !people.participants.some(p => p.role === 'ACCEPT' && p.active)) blocker = '尚未设置有效验收人员'
    if (!blocker && action.value === 'TESTING' && !['NOT_REQUIRED', 'DONE'].includes(workflow.design_status)) blocker = '设计尚未完成'
    if (item.revision !== workflow.revision || item.revision !== people.revision) blocker = '信息已变化，请重新检查'
    return { id, title, revision: item.revision, blocker, delegated }
  } catch (e) { return { id, title, revision: 0, blocker: actionErrorMessage(e), delegated: false } }
}
async function check() {
  if (busy.value || !selected.value.length || selected.value.length > 50 || !auth.hasPermission(permission.value)) return
  const request = ++sequence
  busy.value = true; error.value = ''; results.value = []; preview.value = []
  const ids = [...selected.value]
  const rows: Preview[] = []
  for (let i = 0; i < ids.length; i += 5) {
    const part = await Promise.all(ids.slice(i, i + 5).map(inspect))
    if (request !== sequence) return
    rows.push(...part)
  }
  if (request === sequence) { preview.value = rows; busy.value = false }
}
async function submit() {
  if (busy.value || !eligible.value.length || results.value.length || !auth.hasPermission(permission.value)) return
  if (reasonRequired.value && reason.value.trim().length < 2) { error.value = '请填写关闭或代操作原因（至少 2 个字符）'; return }
  const request = ++sequence
  busy.value = true; error.value = ''
  try {
    const payload = { action: action.value, items: eligible.value.map(({ id, revision }) => ({ id, revision })), reason: reason.value.trim() || null } as BatchPayload
    const response = await batchActions(props.kind, payload)
    if (request !== sequence) return
    results.value = response.results
    emit('updated')
  } catch (e) {
    if (request === sequence) { error.value = `${actionErrorMessage(e)}。请刷新列表核对实际结果后重新选择。`; preview.value = [] }
  } finally { if (request === sequence) busy.value = false }
}
</script>
<template>
  <el-button v-if="auth.hasPermission(permission)" :disabled="!rows.length" @click="begin">批量操作</el-button>
  <el-dialog :model-value="open" title="批量操作" width="min(720px, calc(100vw - 24px))" append-to-body :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" @close="close">
    <p>选择当前列表中的记录，每次最多 50 条。检查后只执行可操作项。</p>
    <el-select v-model="action" aria-label="批量操作类型" :disabled="busy || results.length > 0" style="width:100%"><el-option v-for="option in options" :key="option.value" :value="option.value" :label="option.label" /></el-select>
    <el-checkbox-group v-model="selected" :max="50" :disabled="busy || results.length > 0" class="batch-selection">
      <el-checkbox v-for="row in rows" :key="row.id" :value="row.id">#{{ row.id }} {{ row.title }}</el-checkbox>
    </el-checkbox-group>
    <ul v-if="preview.length" class="batch-preview" aria-label="操作前检查">
      <li v-for="row in preview" :key="row.id"><strong>{{ row.title }}</strong><span>{{ row.blocker || (row.delegated ? '可操作，需填写代操作原因' : '可操作') }}</span></li>
    </ul>
    <el-form v-if="preview.length && !results.length" label-position="top" @submit.prevent="submit">
      <el-form-item :label="reasonRequired ? '关闭或代操作原因' : '说明（选填）'" :required="reasonRequired"><el-input v-model="reason" type="textarea" :maxlength="500" :disabled="busy" /></el-form-item>
    </el-form>
    <ul v-if="results.length" class="batch-preview" aria-label="批量操作结果">
      <li v-for="row in results" :key="row.id"><strong>#{{ row.id }} {{ row.success ? '成功' : '未完成' }}</strong><span>{{ row.message }}</span></li>
    </ul>
    <p v-if="error" role="alert">{{ error }}</p>
    <template #footer>
      <el-button :disabled="busy" @click="close">{{ results.length ? '完成' : '取消' }}</el-button>
      <el-button v-if="!results.length" :disabled="busy || !selected.length" @click="check">检查所选记录</el-button>
      <el-button v-if="preview.length && !results.length" type="primary" :loading="busy" :disabled="!eligible.length" @click="submit">执行可操作的 {{ eligible.length }} 项</el-button>
    </template>
  </el-dialog>
</template>
<style scoped>
.batch-selection { display: flex; flex-direction: column; max-height: 260px; overflow: auto; margin-block: 16px; }
.batch-selection :deep(.el-checkbox) { min-height: 44px; height: auto; margin-right: 0; }
.batch-selection :deep(.el-checkbox__label) { white-space: normal; overflow-wrap: anywhere; }
.batch-preview { list-style: none; padding: 0; max-height: 240px; overflow: auto; }
.batch-preview li { padding: 8px 0; border-bottom: 1px solid var(--if-border); }
.batch-preview span { display: block; margin-top: 4px; overflow-wrap: anywhere; }
</style>
