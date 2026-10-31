<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { actWorkflow, getWorkflow, getParticipants, type Workflow, type WorkflowAction, type Participants } from '@/api/collaboration'
import { useAuthStore } from '@/stores/auth'
import { availableRequirementStatusActions, requirementStatusLabel, type ReqStatusAction } from '@/constants/requirement'
import { formatLocalDateTime } from '@/utils/dates'
import type { Requirement } from '@/types/domain'
import CollaborationPeople from './CollaborationPeople.vue'
import SectionCard from './ui/SectionCard.vue'
const props = defineProps<{ item: Requirement; readonly?: boolean }>()
const emit = defineEmits<{ updated: []; status: [action: ReqStatusAction] }>()
const auth = useAuthStore()
const flow = ref<Workflow | null>(null)
const people = ref<Participants['participants']>([])
const failed = ref(false)
const busy = ref(false)
const reason = ref('')
const pending = ref<WorkflowAction['action'] | null>(null)
const steps = ['DRAFT', 'CONFIRMED', 'DEVELOPING', 'TESTING', 'DONE', 'ONLINE']
const roles = ['CONFIRM', 'DEVELOP', 'DEVELOP', 'ACCEPT', '', '']
const designLabels = { NOT_REQUIRED: '不需要设计', PENDING: '未开始', IN_PROGRESS: '进行中', DONE: '已完成' }
const actionLabels: Record<string, string> = { CONFIRM: '确认当前内容', REQUEST_CHANGES: '要求补充说明', DESIGN_PENDING: '启用 / 重新打开设计', DESIGN_START: '开始设计', DESIGN_DONE: '完成设计', DESIGN_CANCEL: '取消设计要求', LEGACY_MIGRATION: '历史数据迁入（未补造确认）' }
const identity = computed(() => `${auth.user?.id}:${auth.accessToken}:${auth.permissionCodes.join(',')}`)
let sequence = 0
async function load() {
  const request = ++sequence
  flow.value = null; people.value = []; failed.value = false; pending.value = null
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
const canRole = (role: string) => people.value.some(p => p.role === role && p.active && p.user_id === auth.user?.id) || !!auth.user?.can_view_api_docs
const names = (role: string) => people.value.filter(p => p.role === role).map(p => p.display_name + (p.active ? '' : '（已停用）')).join('、') || '待分配'
const actions = computed(() => availableRequirementStatusActions(props.item.status, canAct.value).filter(a => {
  if (a.target === 'CONFIRMED' && props.item.status === 'DRAFT') return false
  if (a.target === 'DEVELOPING') return canRole(props.item.status === 'TESTING' ? 'ACCEPT' : 'DEVELOP')
  if (a.target === 'TESTING') return canRole('DEVELOP')
  if (a.target === 'DONE') return canRole('ACCEPT')
  return true
}))
const designActions = computed<WorkflowAction['action'][]>(() => {
  if (!flow.value || !canAct.value || !canRole('DESIGN') || !['CONFIRMED', 'DEVELOPING'].includes(props.item.status)) return []
  return ({ NOT_REQUIRED: ['DESIGN_PENDING'], PENDING: ['DESIGN_START', 'DESIGN_CANCEL'], IN_PROGRESS: ['DESIGN_DONE', 'DESIGN_CANCEL'], DONE: ['DESIGN_PENDING', 'DESIGN_CANCEL'] } as Record<string, WorkflowAction['action'][]>)[flow.value.design_status] || []
})
function begin(action: WorkflowAction['action']) { pending.value = action; reason.value = '' }
async function submit() {
  if (!flow.value || !pending.value) return
  busy.value = true
  try { await actWorkflow(props.item.id, { action: pending.value, revision: flow.value.revision, reason: reason.value.trim() || null }); pending.value = null; emit('updated') }
  catch { /* Keep the form; never silently replay a conflicting write. */ }
  finally { busy.value = false }
}
function recordLabel(action: string) { return actionLabels[action] || requirementStatusLabel[action.replace('STATUS_', '')] || action }
</script>
<template>
  <SectionCard title="需求进度" description="确认、开发、验收与上线记录">
    <p v-if="failed">进度加载失败 <el-button link @click="load">重试</el-button></p>
    <template v-else-if="flow">
      <el-alert v-if="item.status === 'PAUSED' || item.status === 'CANCELED'" :title="`${requirementStatusLabel[item.status]}${flow.paused_from ? ' · 暂停前：' + requirementStatusLabel[flow.paused_from] : ''}`" type="warning" :closable="false" />
      <el-alert v-if="flow.needs_confirmation" title="当前内容待确认；修改范围或验收标准后，需要重新确认才能继续流转。" type="warning" :closable="false" />
      <p v-if="flow.legacy_completed">历史完成记录：保留原发布资格，不补造人员确认。</p>
      <ol class="progress-steps" aria-label="需求阶段">
        <li v-for="(step, index) in steps" :key="step" :class="{ current: current === index, completed: current > index }" :aria-current="current === index ? 'step' : undefined">
          <span class="step-dot" aria-hidden="true">{{ current > index ? '✓' : current === index ? '●' : index + 1 }}</span>
          <div><strong>{{ requirementStatusLabel[step] }}</strong><small>{{ current === index ? (item.status === 'PAUSED' ? '暂停于此' : '当前阶段') : current > index ? '已流转' : '尚未到达' }}</small>
            <p v-if="roles[index]">{{ names(roles[index]!) }}</p>
            <p v-if="step === 'DRAFT'">{{ flow.needs_confirmation ? '等待确认当前内容' : flow.records.some(r => r.action === 'CONFIRM' || r.action === 'STATUS_CONFIRMED') ? '当前内容已确认' : '历史阶段兼容，未补造确认' }}</p>
            <p v-if="step === 'DEVELOPING'">设计：{{ designLabels[flow.design_status] }} · {{ names('DESIGN') }}</p>
            <p v-if="step === 'DONE'">{{ item.current_version_id ? `所属版本 #${item.current_version_id}` : '尚未关联版本，无法发布' }}</p>
            <p v-if="step === 'ONLINE'">{{ item.status === 'ONLINE' ? '版本已实际发布' : '等待版本实际发布' }}</p>
          </div>
        </li>
      </ol>
      <div v-if="canAct" class="progress-actions">
        <el-button v-if="item.status === 'DRAFT' && canRole('CONFIRM')" @click="begin('REQUEST_CHANGES')">要求补充说明</el-button>
        <el-button v-if="flow.needs_confirmation && canRole('CONFIRM')" type="primary" @click="begin('CONFIRM')">确认当前内容</el-button>
        <el-button v-for="action in actions" :key="action.target" @click="emit('status', action)">{{ action.label }}</el-button>
        <el-button v-for="action in designActions" :key="action" @click="begin(action)">{{ actionLabels[action] }}</el-button>
      </div>
      <CollaborationPeople v-if="!readonly" kind="requirement" :id="item.id" :revision="item.revision" :editable="auth.hasPermission('rd.requirement.edit') && !['ONLINE', 'CANCELED'].includes(item.status)" @updated="emit('updated')" />
      <details class="progress-history"><summary>查看流转与确认记录（最近 {{ flow.records.length }} 条）</summary>
        <p v-if="!flow.records.length">尚无确认或流转记录。</p>
        <article v-for="record in flow.records" :key="record.id"><strong>{{ recordLabel(record.action) }}</strong> · {{ record.actor_id ? `${record.detail.actor_name || '实际操作人'} #${record.actor_id}` : '历史迁移' }} · {{ formatLocalDateTime(record.created_at) }}<p v-if="record.detail.reason">{{ record.detail.reason }}</p><details v-if="record.detail.description"><summary>当时确认的内容</summary><p class="multiline">{{ record.detail.description }}</p><p class="multiline">{{ record.detail.acceptance_criteria }}</p></details></article>
      </details>
    </template>
    <p v-else>正在加载进度…</p>
    <el-dialog :model-value="pending !== null" :title="pending ? actionLabels[pending] : ''" width="min(520px, calc(100vw - 24px))" append-to-body @close="pending = null">
      <el-form label-position="top" @submit.prevent="submit"><el-form-item label="说明（取消、重开设计或管理员代操作必填）"><el-input v-model="reason" type="textarea" maxlength="500" /></el-form-item><el-button type="primary" native-type="submit" :loading="busy">确认操作</el-button></el-form>
    </el-dialog>
  </SectionCard>
</template>
<style scoped>
.progress-steps { list-style: none; padding: 12px 0 0; margin: 0; }
.progress-steps li { position: relative; display: flex; gap: 16px; padding-bottom: 24px; }
.progress-steps li:not(:last-child)::before { content: ''; position: absolute; left: 15px; top: 32px; bottom: 0; width: 2px; background: var(--if-border, #ddd); }
.step-dot { flex: 0 0 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; background: var(--if-bg-muted, #eee); }
.current .step-dot { background: var(--el-color-primary); color: white; }.completed .step-dot { background: var(--el-color-success-light-8); color: var(--el-color-success-dark-2); }
small { margin-left: 12px; color: var(--if-text-3); }p { margin: 8px 0; overflow-wrap: anywhere; }.progress-actions { display: flex; gap: 8px; flex-wrap: wrap; }.progress-actions .el-button { margin: 0; }.progress-history { margin-top: 20px; }.progress-history article { border-top: 1px solid var(--if-border, #eee); padding: 12px 0; }.multiline { white-space: pre-wrap; }summary { cursor: pointer; }
</style>
