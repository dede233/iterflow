<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getCollaborators, replaceCollaborators, type Collaborators } from '@/api/requirementCollaboration'
import { getRequirement } from '@/api/requirements'
import { useRevisionConflict } from '@/composables/useRevisionConflict'
import { requirementConflictSummary } from '@/utils/revisionSummaries'
import { usePermission } from '@/composables/usePermission'
import { useResponsive } from '@/composables/useResponsive'
import SectionCard from '@/components/ui/SectionCard.vue'
import RevisionConflictDialog from '@/components/RevisionConflictDialog.vue'
import RequirementAssigneeSelect from '@/components/RequirementAssigneeSelect.vue'
const props = defineProps<{ requirementId: number; revision: number }>()
const emit = defineEmits<{ updated: [] }>()
const { can } = usePermission()
const { isMobile } = useResponsive()
const conflict = useRevisionConflict()
const data = ref<Collaborators | null>(null)
const failed = ref(false)
const loading = ref(false)
const dialog = ref(false)
const saving = ref(false)
const form = reactive({ owner_id: null as number | null, developer_ids: [] as number[], designer_ids: [] as number[], revision: 1 })
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
async function open(): Promise<void> {
  await load()
  if (!data.value) return
  Object.assign(form, { owner_id: data.value.owner?.user_id ?? null, developer_ids: data.value.developers.map(p => p.user_id), designer_ids: data.value.designers.map(p => p.user_id), revision: data.value.revision })
  dialog.value = true
}
async function save(): Promise<void> {
  if (saving.value) return
  saving.value = true
  try {
    data.value = await replaceCollaborators(props.requirementId, { ...form })
    dialog.value = false
    ElMessage.success('协作人员已更新')
    emit('updated')
  } catch (error) {
    await conflict.show(error, form.revision, { entityLabel: '需求', getLatest: () => getRequirement(props.requirementId), summarize: requirementConflictSummary, apply: async () => { dialog.value = false; emit('updated'); await load() } })
  } finally { saving.value = false }
}
onMounted(load)
watch(() => [props.requirementId, props.revision], load)
</script>
<template>
  <SectionCard v-loading="loading" title="协作人员" description="总负责人协调需求，开发与设计可多人协作。">
    <el-button v-if="failed" @click="load">协作人员加载失败，重试</el-button>
    <template v-else-if="data">
      <dl class="collaborators">
        <dt>总负责人</dt><dd>{{ data.owner?.display_name ?? '未分配' }}</dd>
        <dt>开发人员</dt><dd>{{ data.developers.map(p => p.display_name).join('、') || '未分配' }}</dd>
        <dt>设计人员</dt><dd>{{ data.designers.map(p => p.display_name).join('、') || '未分配' }}</dd>
      </dl>
      <el-button v-if="can('rd.requirement.edit')" :disabled="loading || saving" @click="open">分配协作人员</el-button>
    </template>
    <el-dialog v-model="dialog" title="分配协作人员" :width="isMobile ? '100%' : '560px'" :fullscreen="isMobile" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving">
      <el-form v-if="data" label-position="top" @submit.prevent="save">
        <el-form-item label="总负责人"><RequirementAssigneeSelect v-model="form.owner_id" kind="OWNER" :selected="data.owner ? [data.owner] : []" /></el-form-item>
        <el-form-item label="开发人员"><RequirementAssigneeSelect v-model="form.developer_ids" kind="DEVELOPER" :selected="data.developers" /></el-form-item>
        <el-form-item label="设计人员"><RequirementAssigneeSelect v-model="form.designer_ids" kind="DESIGNER" :selected="data.designers" /></el-form-item>
        <p class="hint">开发和设计候选需要对应启用角色。分工变化后，相关人员会收到站内通知。</p>
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
</style>
