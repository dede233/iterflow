<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getFeedbackCollaboration, getParticipants, setParticipants, setRecipients, transferFeedback, type FeedbackCollaboration, type Participant, type Person } from '@/api/collaboration'
import { useAuthStore } from '@/stores/auth'
import { formatLocalDateTime } from '@/utils/dates'
import PeopleSelector from './PeopleSelector.vue'
import SectionCard from './ui/SectionCard.vue'
const props = defineProps<{ kind: 'feedback' | 'requirement'; id: number; revision: number; editable: boolean }>()
const emit = defineEmits<{ updated: []; loaded: [data: FeedbackCollaboration | null] }>()
const auth = useAuthStore()
const feedback = ref<FeedbackCollaboration | null>(null)
const selected = ref<Person[]>([])
const recipients = ref<number[]>([])
const roles = ref<Record<string, number[]>>({ CONFIRM: [], DESIGN: [], DEVELOP: [], ACCEPT: [] })
const roleLabels = { CONFIRM: '需求确认人', DESIGN: '设计人员', DEVELOP: '开发人员', ACCEPT: '验收人员' }
const editing = ref(false)
const failed = ref(false)
const loaded = ref(false)
const saving = ref(false)
const revision = ref(0)
const handler = ref<number | null>(null)
const reason = ref('')
let sequence = 0
const identity = computed(() => `${auth.user?.id}:${auth.accessToken}:${auth.permissionCodes.join(',')}`)
async function load() {
  const request = ++sequence
  emit('loaded', null)
  loaded.value = false; failed.value = false; editing.value = false; feedback.value = null
  selected.value = []; recipients.value = []; roles.value = { CONFIRM: [], DESIGN: [], DEVELOP: [], ACCEPT: [] }
  if (!auth.hasPermission(`rd.${props.kind}.view`)) return
  try {
    if (props.kind === 'feedback') {
      const data = await getFeedbackCollaboration(props.id)
      if (request !== sequence) return
      feedback.value = data; revision.value = data.revision; selected.value = data.recipients
      emit('loaded', data)
      recipients.value = data.recipients.map(p => p.id); handler.value = data.handler_id; reason.value = ''
    } else {
      const data = await getParticipants(props.id)
      if (request !== sequence) return
      revision.value = data.revision
      selected.value = data.participants.map(p => ({ id: p.user_id, display_name: p.display_name + (p.active ? '' : '（已停用）') }))
      for (const person of data.participants) roles.value[person.role]!.push(person.user_id)
    }
    loaded.value = true
  } catch { if (request === sequence) failed.value = true }
}
watch(() => [props.id, props.revision, props.kind, identity.value], load, { immediate: true, flush: 'sync' })
onScopeDispose(() => { sequence++ })
function name(id: number | null) { return id == null ? '待分配' : selected.value.find(p => p.id === id)?.display_name || `用户 #${id}` }
async function save() {
  if (props.kind === 'feedback' && !recipients.value.length) { ElMessage.warning('至少选择一位接收人'); return }
  saving.value = true
  try {
    if (props.kind === 'feedback') await setRecipients(props.id, revision.value, recipients.value)
    else await setParticipants(props.id, revision.value, Object.entries(roles.value).flatMap(([role, ids]) => ids.map(user_id => ({ role: role as Participant['role'], user_id }))))
    emit('updated'); await load()
  } catch { /* Shared API handler reports conflicts; retain the user's choices. */ }
  finally { saving.value = false }
}
async function transfer() {
  if (!handler.value || reason.value.trim().length < 2) { ElMessage.warning('请选择处理人并填写转交原因'); return }
  saving.value = true
  try { await transferFeedback(props.id, revision.value, handler.value, reason.value.trim()); emit('updated'); await load() }
  catch { /* Keep input for manual conflict reconciliation. */ }
  finally { saving.value = false }
}
</script>
<template>
  <SectionCard :title="kind === 'feedback' ? '接收与处理' : '环节人员'" class="people-panel">
    <p v-if="failed">协作信息加载失败 <el-button link @click="load">重试</el-button></p>
    <template v-else-if="loaded">
      <template v-if="kind === 'feedback'">
        <p>接收人：{{ selected.map(p => p.display_name).join('、') || '历史反馈，尚未设置接收人' }}</p>
        <p>当前处理人：{{ name(feedback?.handler_id ?? null) }}</p>
        <p v-if="feedback?.accepted_by">由 {{ name(feedback.accepted_by) }} 于 {{ formatLocalDateTime(feedback.accepted_at!) }} 确认受理</p>
        <p v-else>本轮尚无受理记录</p>
      </template>
      <dl v-else><div v-for="(label, role) in roleLabels" :key="role"><dt>{{ label }}</dt><dd>{{ roles[role]!.map(id => name(id)).join('、') || '待分配' }}</dd></div></dl>
      <el-button v-if="editable && !editing" @click="editing = true">调整人员</el-button>
      <el-form v-if="editing && editable" label-position="top">
        <el-form-item v-if="kind === 'feedback'" label="反馈接收人" required><PeopleSelector v-model="recipients" kind="feedback" :feedback-id="id" :selected="selected" multiple /></el-form-item>
        <template v-else><el-form-item v-for="(label, role) in roleLabels" :key="role" :label="label"><PeopleSelector v-model="roles[role]!" kind="requirement" :selected="selected" :multiple="role !== 'CONFIRM'" /></el-form-item></template>
        <el-button :disabled="saving" @click="load">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存人员</el-button>
        <template v-if="kind === 'feedback' && feedback?.accepted_by">
          <el-divider />
          <el-form-item label="转交给"><el-select v-model="handler"><el-option v-for="person in selected" :key="person.id" :label="person.display_name" :value="person.id" /></el-select></el-form-item>
          <el-form-item label="转交原因"><el-input v-model="reason" type="textarea" maxlength="500" /></el-form-item>
          <el-button :loading="saving" @click="transfer">转交处理</el-button>
        </template>
      </el-form>
    </template>
    <p v-else>正在加载协作信息…</p>
  </SectionCard>
</template>
<style scoped>
.people-panel { margin-top: 20px; }
dl > div { display: flex; gap: 16px; margin: 12px 0; }
dt { min-width: 90px; color: var(--if-text-3); }
dd { margin: 0; overflow-wrap: anywhere; }
.el-form { margin-top: 16px; }
</style>
