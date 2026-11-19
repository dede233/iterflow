<script setup lang="ts">
import { computed, nextTick, onScopeDispose, reactive, ref, watch } from 'vue'
import { getParticipants, setParticipants, type Participant, type Participants, type Person } from '@/api/collaboration'
import { useAuthStore } from '@/stores/auth'
import { actionErrorMessage } from '@/utils/actionError'
import PeopleSelector from './PeopleSelector.vue'

const props = defineProps<{ id: number; roles: Participant['role'][]; title: string; requiredRoles?: Participant['role'][] }>()
const emit = defineEmits<{ close: []; updated: [] }>()
const auth = useAuthStore()
type Role = Participant['role']
const labels = { CONFIRM: '需求确认人', DESIGN: '设计人员（可选）', DEVELOP: '开发人员', ACCEPT: '验收人员' }
const formRoot = ref<HTMLElement>()
const data = ref<Participants | null>(null)
const choices = ref<Record<Role, number[]>>({ CONFIRM: [], DESIGN: [], DEVELOP: [], ACCEPT: [] })
const loading = ref(false)
const failed = ref(false)
const saving = ref(false)
const saveError = ref('')
const submitted = ref(false)
const selected = computed(() => data.value?.participants.map(p => ({ id: p.user_id, display_name: p.display_name + (p.active ? '' : '（已停用）') })) ?? [])
const inactive = computed(() => data.value?.participants.filter(person => !person.active) ?? [])
const developerOptions = reactive(new Map<number, Person>())
const acceptanceOptions = computed(() => [
  ...selected.value,
  ...[...developerOptions.values()].filter(person => choices.value.ACCEPT.includes(person.id)),
])
// The full replacement request cannot retain a disabled user in another role.
const editableRoles = computed(() => [...new Set([...props.roles, ...inactive.value.map(person => person.role)])])
const canCopyDevelopers = computed(() => editableRoles.value.includes('DEVELOP') && editableRoles.value.includes('ACCEPT'))
const developersToAdd = computed(() => choices.value.DEVELOP.filter(id =>
  !inactive.value.some(person => person.user_id === id) && !choices.value.ACCEPT.includes(id),
))
function rememberDevelopers(role: Role, people: Person[]) {
  if (role === 'DEVELOP') people.forEach(person => developerOptions.set(person.id, person))
}
function addDevelopersToAcceptance() {
  if (!canCopyDevelopers.value || !developersToAdd.value.length || saving.value) return
  choices.value.ACCEPT = [...new Set([...choices.value.ACCEPT, ...developersToAdd.value])]
}
const required = (role: Role) => props.requiredRoles?.includes(role) ?? false
function fieldError(role: Role): string {
  if (!submitted.value) return ''
  if (choices.value[role].some(id => inactive.value.some(person => person.user_id === id))) return '请移除已停用人员，或选择其他人员'
  if (required(role) && choices.value[role].length === 0) return `请至少选择一名${labels[role]}`
  return ''
}
const canEdit = computed(() => auth.hasPermission('rd.requirement.view') && auth.hasPermission('rd.requirement.edit'))
let sequence = 0
async function load() {
  const request = ++sequence
  data.value = null; loading.value = true; failed.value = false; saveError.value = ''; saving.value = false; submitted.value = false
  choices.value = { CONFIRM: [], DESIGN: [], DEVELOP: [], ACCEPT: [] }
  developerOptions.clear()
  if (!canEdit.value) { loading.value = false; return }
  try {
    const result = await getParticipants(props.id)
    if (request !== sequence) return
    data.value = result
    for (const p of result.participants) choices.value[p.role].push(p.user_id)
  } catch { if (request === sequence) failed.value = true }
  finally { if (request === sequence) loading.value = false }
}
watch(() => [props.id, props.roles.join(','), auth.user?.id, auth.accessToken, auth.permissionCodes.join(',')], load, { immediate: true, flush: 'sync' })
onScopeDispose(() => { sequence++ })
async function save() {
  if (!data.value || !canEdit.value || saving.value) return
  submitted.value = true
  saveError.value = ''
  const invalidRole = editableRoles.value.find(role => fieldError(role))
  if (invalidRole) {
    await nextTick()
    const input = formRoot.value?.querySelector<HTMLElement>(`[data-role="${invalidRole}"] input`)
    input?.focus()
    input?.scrollIntoView?.({ block: 'nearest' })
    return
  }
  const request = sequence
  // The API replaces the full participant set. Preserve roles outside this editor.
  const participants: Participant[] = [
    ...data.value.participants.filter(p => !editableRoles.value.includes(p.role)).map(({ role, user_id }) => ({ role, user_id })),
    ...editableRoles.value.flatMap(role => choices.value[role].map(user_id => ({ role, user_id }))),
  ]
  saving.value = true
  try {
    await setParticipants(props.id, data.value.revision, participants)
    if (request !== sequence) return
    emit('updated'); emit('close')
  } catch (error) { if (request === sequence) saveError.value = actionErrorMessage(error) }
  finally { if (request === sequence) saving.value = false }
}
</script>
<template>
  <el-dialog :model-value="true" :title="title" width="min(520px, calc(100vw - 24px))" append-to-body :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving" @close="emit('close')">
    <p v-if="loading">正在加载人员…</p>
    <p v-else-if="failed">人员加载失败 <el-button link @click="load">重试</el-button></p>
    <div v-else-if="data && canEdit" ref="formRoot">
      <el-form label-position="top" @submit.prevent="save">
        <p class="people-hint">保存人员后，仍需由对应人员执行确认或阶段操作。</p>
        <p v-if="editableRoles.includes('CONFIRM')" class="people-hint">需求确认人可多选，由任意一名有权限的确认人确认即可。</p>
        <p v-if="editableRoles.includes('ACCEPT')" class="people-hint">验收人员可多选，由任意一名有权限的验收人员确认通过即可。</p>
        <p v-if="editableRoles.length > 1" class="people-hint">同一人可以承担多个角色。</p>
        <el-form-item v-for="role in editableRoles" :key="role" :data-role="role" :label="labels[role]" :required="required(role)" :error="fieldError(role)">
          <PeopleSelector v-model="choices[role]" kind="requirement" :selected="role === 'ACCEPT' ? acceptanceOptions : selected" :multiple="true" :disabled="saving" :aria-invalid="!!fieldError(role)" @people-added="rememberDevelopers(role, $event)" />
          <el-button v-if="role === 'ACCEPT' && canCopyDevelopers" class="acceptance-copy" link type="primary" native-type="button" :disabled="saving || !developersToAdd.length" @click="addDevelopersToAcceptance">将开发人员加入验收</el-button>
        </el-form-item>
        <p v-if="saveError" role="alert">{{ saveError }} 所选人员已保留。<el-button link @click="load">重新加载人员</el-button></p>
        <el-button :disabled="saving" @click="emit('close')">取消</el-button>
        <el-button type="primary" native-type="submit" :loading="saving">保存人员</el-button>
      </el-form>
    </div>
  </el-dialog>
</template>
<style scoped>
.people-hint { margin: 0 0 16px; color: var(--if-text-3); font-size: 13px; }
.acceptance-copy { min-height: 32px; }
@media (max-width: 767px) { .acceptance-copy { min-height: 44px; } }
</style>
