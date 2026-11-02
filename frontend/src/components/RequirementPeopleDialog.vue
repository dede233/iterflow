<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { getParticipants, setParticipants, type Participant, type Participants } from '@/api/collaboration'
import { useAuthStore } from '@/stores/auth'
import PeopleSelector from './PeopleSelector.vue'

const props = defineProps<{ id: number; roles: Participant['role'][]; title: string }>()
const emit = defineEmits<{ close: []; updated: [] }>()
const auth = useAuthStore()
const labels = { CONFIRM: '需求确认人', DESIGN: '设计人员（可选）', DEVELOP: '开发人员', ACCEPT: '验收人员' }
const data = ref<Participants | null>(null)
const choices = ref<Record<Participant['role'], number[]>>({ CONFIRM: [], DESIGN: [], DEVELOP: [], ACCEPT: [] })
const loading = ref(false)
const failed = ref(false)
const saving = ref(false)
const saveFailed = ref(false)
const selected = computed(() => data.value?.participants.map(p => ({ id: p.user_id, display_name: p.display_name + (p.active ? '' : '（已停用）') })) ?? [])
const canEdit = computed(() => auth.hasPermission('rd.requirement.view') && auth.hasPermission('rd.requirement.edit'))
let sequence = 0
async function load() {
  const request = ++sequence
  data.value = null; loading.value = true; failed.value = false; saveFailed.value = false; saving.value = false
  choices.value = { CONFIRM: [], DESIGN: [], DEVELOP: [], ACCEPT: [] }
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
  const request = sequence
  // The API replaces the full participant set. Preserve roles outside this editor.
  const participants: Participant[] = [
    ...data.value.participants.filter(p => !props.roles.includes(p.role)).map(({ role, user_id }) => ({ role, user_id })),
    ...props.roles.flatMap(role => choices.value[role].map(user_id => ({ role, user_id }))),
  ]
  saving.value = true; saveFailed.value = false
  try {
    await setParticipants(props.id, data.value.revision, participants)
    if (request !== sequence) return
    emit('updated'); emit('close')
  } catch { if (request === sequence) saveFailed.value = true }
  finally { if (request === sequence) saving.value = false }
}
</script>
<template>
  <el-dialog :model-value="true" :title="title" width="min(520px, calc(100vw - 24px))" append-to-body :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving" @close="emit('close')">
    <p v-if="loading">正在加载人员…</p>
    <p v-else-if="failed">人员加载失败 <el-button link @click="load">重试</el-button></p>
    <el-form v-else-if="data && canEdit" label-position="top" @submit.prevent="save">
      <p class="people-hint">保存人员后，仍需由对应人员执行确认或阶段操作。</p>
      <el-form-item v-for="role in roles" :key="role" :label="labels[role]">
        <PeopleSelector v-model="choices[role]" kind="requirement" :selected="selected" :multiple="role === 'DESIGN' || role === 'DEVELOP'" :disabled="saving" />
      </el-form-item>
      <p v-if="saveFailed" role="alert">保存失败，所选人员已保留。若信息已更新，请重新加载后调整。<el-button link @click="load">重新加载人员</el-button></p>
      <el-button :disabled="saving" @click="emit('close')">取消</el-button>
      <el-button type="primary" native-type="submit" :loading="saving">保存人员</el-button>
    </el-form>
  </el-dialog>
</template>
<style scoped>
.people-hint { margin: 0 0 16px; color: var(--if-text-3); font-size: 13px; }
</style>
