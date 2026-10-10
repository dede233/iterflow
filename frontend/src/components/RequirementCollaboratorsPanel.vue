<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getCollaborators, updateCollaboratorGroup, confirmDevelopmentCompletion, type Collaborators } from '@/api/requirementCollaboration'
import { getRequirement } from '@/api/requirements'
import { useRevisionConflict } from '@/composables/useRevisionConflict'
import { requirementConflictSummary } from '@/utils/revisionSummaries'
import { usePermission } from '@/composables/usePermission'
import { useResponsive } from '@/composables/useResponsive'
import { useAuthStore } from '@/stores/auth'
import SectionCard from '@/components/ui/SectionCard.vue'
import RevisionConflictDialog from '@/components/RevisionConflictDialog.vue'
import RequirementAssigneeSelect from '@/components/RequirementAssigneeSelect.vue'
const props = defineProps<{ requirementId: number; revision: number; status: string }>()
const emit = defineEmits<{ updated: []; 'completion-ready': [ready: boolean] }>()
const { can } = usePermission()
const auth = useAuthStore()
const { isMobile } = useResponsive()
const conflict = useRevisionConflict()
const data = ref<Collaborators | null>(null)
const failed = ref(false)
const loading = ref(false)
const dialog = ref(false)
const saving = ref(false)
const form = reactive({ kind: 'OWNER' as 'OWNER' | 'DEVELOPMENT' | 'DESIGN', owner_id: null as number | null, user_ids: [] as number[], revision: 1 })
const completionStages = ['DEVELOPING', 'TESTING', 'DONE']
const myCompletion = computed(() => data.value?.development_completions.find(p => p.user_id === auth.user?.id))
const canConfirm = computed(() => can('rd.requirement.status') && completionStages.includes(props.status) && myCompletion.value?.completed_at === null)
const completedCount = computed(() => data.value?.development_completions.filter(p => p.completed_at !== null).length ?? 0)
const completionReady = computed(() => !!data.value?.developers.length && data.value.developers.every(developer => data.value?.development_completions.some(p => p.user_id === developer.user_id && p.completed_at !== null)))
watch(() => !loading.value && !failed.value && completionReady.value, ready => emit('completion-ready', ready), { immediate: true })
async function confirmMine(): Promise<void> {
  if (saving.value || !canConfirm.value || !data.value) return
  const revision = data.value.revision
  saving.value = true
  try {
    data.value = await confirmDevelopmentCompletion(props.requirementId, revision)
    ElMessage.success('已确认本人开发完成')
    emit('updated')
  } catch (error) {
    await conflict.show(error, revision, { entityLabel: '需求', getLatest: () => getRequirement(props.requirementId), summarize: requirementConflictSummary, apply: async () => { emit('updated'); await load() } })
  } finally { saving.value = false }
}
let generation = 0
async function load(): Promise<void> {
  const run = ++generation
  loading.value = true
  failed.value = false
  try {
    const result = await getCollaborators(props.requirementId)
    if (run === generation) data.value = result
  } catch {
    if (run === generation) { failed.value = true; data.value = null }
  } finally { if (run === generation) loading.value = false }
}
async function open(kind: typeof form.kind): Promise<void> {
  await load()
  if (!data.value) return
  Object.assign(form, { kind, owner_id: data.value.owner?.user_id ?? null, user_ids: (kind === 'DESIGN' ? data.value.designers : data.value.developers).map(p => p.user_id), revision: data.value.revision })
  dialog.value = true
}
async function save(): Promise<void> {
  if (saving.value) return
  if (form.kind !== 'OWNER' && !form.user_ids.length) { ElMessage.warning('当前阶段至少选择一名参与人员'); return }
  saving.value = true
  try {
    const payload = form.kind === 'OWNER' ? { kind: form.kind, revision: form.revision, owner_id: form.owner_id } : { kind: form.kind, revision: form.revision, user_ids: [...form.user_ids] }
    data.value = await updateCollaboratorGroup(props.requirementId, payload)
    dialog.value = false
    ElMessage.success('人员分工已更新')
    emit('updated')
  } catch (error) {
    await conflict.show(error, form.revision, { entityLabel: '需求', getLatest: () => getRequirement(props.requirementId), summarize: requirementConflictSummary, apply: async () => { dialog.value = false; emit('updated'); await load() } })
  } finally { saving.value = false }
}
onMounted(load)
watch(() => [props.requirementId, props.revision], load)
</script>
<template>
  <SectionCard v-loading="loading" title="协作人员" description="按需求进度分配，开始设计或开发时选择对应人员。">
    <el-button v-if="failed" @click="load">协作人员加载失败，重试</el-button>
    <template v-else-if="data">
      <dl class="collaborators">
        <dt>总负责人</dt><dd>{{ data.owner?.display_name ?? '未分配' }}</dd>
        <template v-if="data.designers.length || status === 'DESIGNING'"><dt>设计人员</dt><dd>{{ data.designers.map(p => p.display_name).join('、') || '未分配' }}</dd></template>
        <template v-if="data.developers.length || ['DEVELOPING','TESTING','DONE','ONLINE'].includes(status)"><dt>开发人员</dt><dd>{{ data.developers.map(p => p.display_name).join('、') || '未分配' }}</dd></template>
      </dl>
      <div v-if="data.developers.length" class="completion-list">
        <p>开发完成确认：{{ completedCount }} / {{ data.developers.length }} 人</p>
        <ul><li v-for="developer in data.developers" :key="developer.user_id">
          <span>{{ developer.display_name }}</span>
          <el-tag :type="data.development_completions.find(p => p.user_id === developer.user_id)?.completed_at ? 'success' : 'info'">
            {{ data.development_completions.find(p => p.user_id === developer.user_id)?.completed_at ? '已完成' : '待确认' }}
          </el-tag>
        </li></ul>
        <el-button v-if="canConfirm" type="primary" :loading="saving" :disabled="loading" @click="confirmMine">确认本人开发完成</el-button>
        <p v-if="completionStages.includes(status)" class="hint">每名开发人员需本人确认完成，全部确认后才能将需求标记为已完成并发布。退回开发会清空此前确认。</p>
      </div>
      <p v-else-if="completionStages.includes(status)" class="hint">尚未分配开发人员，不能将需求标记为已完成或发布；请先调整开发人员。</p>
      <div v-if="can('rd.requirement.edit')" class="assignment-actions">
        <el-button :disabled="loading || saving" @click="open('OWNER')">设置总负责人</el-button>
        <el-button v-if="status === 'DESIGNING'" :disabled="loading || saving" @click="open('DESIGN')">调整设计人员</el-button>
        <el-button v-if="['DEVELOPING','TESTING','DONE'].includes(status)" :disabled="loading || saving" @click="open('DEVELOPMENT')">调整开发人员</el-button>
      </div>
      <p v-if="['DRAFT','CONFIRMED','PLANNED'].includes(status)" class="hint">需要设计时，在“开始设计”中选择设计人员；“开始开发”时再选择开发人员。</p>
    </template>
    <el-dialog v-model="dialog" :title="form.kind === 'OWNER' ? '设置总负责人' : form.kind === 'DESIGN' ? '调整设计人员' : '调整开发人员'" :width="isMobile ? '100%' : '560px'" :fullscreen="isMobile" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving" destroy-on-close>
      <el-form v-if="data" label-position="top" @submit.prevent="save">
        <el-form-item v-if="form.kind === 'OWNER'" label="总负责人"><RequirementAssigneeSelect v-model="form.owner_id" kind="OWNER" :selected="data.owner ? [data.owner] : []" /></el-form-item>
        <el-form-item v-else :label="form.kind === 'DESIGN' ? '设计人员' : '开发人员'" required><RequirementAssigneeSelect v-model="form.user_ids" :kind="form.kind === 'DESIGN' ? 'DESIGNER' : 'DEVELOPER'" :selected="form.kind === 'DESIGN' ? data.designers : data.developers" /></el-form-item>
      </el-form>
      <template #footer><el-button :disabled="saving" @click="dialog = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存分工</el-button></template>
    </el-dialog>
    <RevisionConflictDialog :visible="conflict.visible" :loading="conflict.loading" :entity-label="conflict.entityLabel" :submitted-revision="conflict.submittedRevision" :metadata="conflict.metadata" :summary="conflict.summary" :read-error="conflict.readError" @close="conflict.close" @reload="conflict.reload" />
  </SectionCard>
</template>
<style scoped>
.collaborators { display: grid; grid-template-columns: 84px minmax(0, 1fr); gap: 12px; margin: 0 0 16px; }
.collaborators dt { color: var(--if-text-2); }
.collaborators dd { margin: 0; overflow-wrap: anywhere; }
.hint { color: var(--if-text-2); font-size: 13px; }
.completion-list { margin-bottom: 16px; }
.completion-list ul { list-style: none; padding: 0; }
.completion-list li { display: flex; gap: 12px; justify-content: space-between; margin: 8px 0; overflow-wrap: anywhere; }
.assignment-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.assignment-actions :deep(.el-button + .el-button) { margin-left: 0; }
</style>
