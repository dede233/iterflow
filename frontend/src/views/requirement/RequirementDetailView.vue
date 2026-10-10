<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  changeRequirementStatus,
  getRequirement,
  listRequirementFeedbacks,
  updateRequirement,
} from '@/api/requirements'
import ScopedRelationLink from '@/components/ScopedRelationLink.vue'
import RequirementAssigneeSelect from '@/components/RequirementAssigneeSelect.vue'
import { getCollaborators, startRequirementStage, type AssigneeOption } from '@/api/requirementCollaboration'
import RequirementCollaboratorsPanel from '@/components/RequirementCollaboratorsPanel.vue'
import { useDetailNavigation } from '@/composables/useDetailNavigation'
import { usePermission } from '@/composables/usePermission'
import { useEditingPresence } from '@/composables/useEditingPresence'
import { useRevisionConflict } from '@/composables/useRevisionConflict'
import { loadRequirementFeedbackSection } from '@/security/detailAuthorization'
import StatusTag from '@/components/StatusTag.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import RevisionConflictDialog from '@/components/RevisionConflictDialog.vue'
import { useResponsive } from '@/composables/useResponsive'
import { formatLocalDateTime } from '@/utils/dates'
import { requirementConflictSummary } from '@/utils/revisionSummaries'
import {
  REQUIREMENT_PRIORITIES,
  REQUIREMENT_TYPES,
  type RequirementPriority,
  availableRequirementStatusActions,
  requirementStatusLabel,
  requirementStatusTagType,
  requirementTypeLabel,
  type ReqStatusAction,
} from '@/constants/requirement'
import type { LinkedFeedback, Requirement } from '@/types/domain'

const props = defineProps<{ embedded?: boolean; embeddedId?: number }>()
const emit = defineEmits<{ updated: []; close: [] }>()
const route = useRoute()
const router = useRouter()
const { backTo, related } = useDetailNavigation('/requirements')
const { can } = usePermission()
const { isMobile } = useResponsive()
const id = Number(props.embedded ? props.embeddedId : route.params.id)
const { start: startPresence, stop: stopPresence, existingEditor } = useEditingPresence('REQUIREMENT', id)
const conflict = useRevisionConflict()

async function showConflict(error: unknown, revision: number, onReload?: (latest: Requirement) => void): Promise<void> {
  await conflict.show(error, revision, {
    entityLabel: '需求',
    getLatest: () => getRequirement(id),
    summarize: requirementConflictSummary,
    apply: (latest) => {
      item.value = latest
      onReload?.(latest)
    },
  })
}

const item = ref<Requirement | null>(null)
const feedbacks = ref<LinkedFeedback[]>([])
const loading = ref(false)
const failed = ref(false)
const canEdit = computed(() => can('rd.requirement.edit'))
const canChangeStatus = computed(() => can('rd.requirement.status'))
const canViewFeedbacks = computed(() => can('rd.feedback.view'))
const statusActions = computed<ReqStatusAction[]>(() =>
  item.value ? availableRequirementStatusActions(item.value.status, canChangeStatus.value).filter(a => !a.startsStage || canEdit.value) : [],
)

// --- status dialog ---
const statusDialog = ref(false)
const statusSubmitting = ref(false)
const currentAction = ref<ReqStatusAction | null>(null)
const statusReason = ref('')
const stagePeople = ref<number[]>([])
const stageSelected = ref<AssigneeOption[]>([])
const stageRevision = ref(1)
const openingStage = ref(false)
const developmentReady = ref(false)

async function openStatusDialog(action: ReqStatusAction): Promise<void> {
  if (openingStage.value) return
  if (action.startsStage) {
    openingStage.value = true
    try {
      const roster = await getCollaborators(id)
      stageSelected.value = action.target === 'DESIGNING' ? roster.designers : roster.developers
      stagePeople.value = stageSelected.value.map(u => u.user_id)
      stageRevision.value = roster.revision
    } catch { ElMessage.error('阶段人员加载失败，请重试'); return }
    finally { openingStage.value = false }
  }
  currentAction.value = action
  statusReason.value = ''
  statusDialog.value = true
}

async function submitStatus(): Promise<void> {
  if (!item.value || !currentAction.value) return
  const action = currentAction.value
  if (action.needsReason && statusReason.value.trim().length < 2) {
    ElMessage.warning('请填写原因（至少 2 个字符）')
    return
  }
  statusSubmitting.value = true
  try {
    if (action.startsStage) {
      if (!stagePeople.value.length) { ElMessage.warning('请至少选择一名阶段人员'); return }
      await startRequirementStage(id, { status: action.target as 'DESIGNING' | 'DEVELOPING', revision: stageRevision.value, user_ids: [...stagePeople.value] })
    } else await changeRequirementStatus(
      item.value.id,
      action.target,
      item.value.revision,
      statusReason.value.trim() || null,
    )
    emit('updated')
    ElMessage.success('状态已更新')
    statusDialog.value = false
    await load()
  } catch (error) {
    await showConflict(error, action.startsStage ? stageRevision.value : item.value.revision, () => { statusDialog.value = false })
  } finally {
    statusSubmitting.value = false
  }
}

// --- edit dialog ---
const editDialog = ref(false)
const editSubmitting = ref(false)
const editForm = reactive({
  title: '',
  requirement_type: '',
  priority: 'P2' as RequirementPriority,
  description: '',
  acceptance_criteria: '',
})

function openEdit(): void {
  if (!item.value || !canEdit.value) return
  fillEditForm(item.value)
  editDialog.value = true
  void startPresence()
}

function fillEditForm(latest: Requirement): void {
  Object.assign(editForm, {
    title: latest.title,
    requirement_type: latest.requirement_type,
    priority: latest.priority,
    description: latest.description,
    acceptance_criteria: latest.acceptance_criteria ?? '',
  })
}

watch(editDialog, (open) => {
  if (!open) void stopPresence()
})

async function submitEdit(): Promise<void> {
  if (!item.value) return
  editSubmitting.value = true
  try {
    await updateRequirement(item.value.id, {
      title: editForm.title.trim(),
      requirement_type: editForm.requirement_type,
      priority: editForm.priority,
      description: editForm.description.trim(),
      acceptance_criteria: editForm.acceptance_criteria.trim() || null,
      revision: item.value.revision,
    })
    emit('updated')
    ElMessage.success('需求已更新')
    editDialog.value = false
    await load()
  } catch (error) {
    await showConflict(error, item.value.revision, fillEditForm)
  } finally {
    editSubmitting.value = false
  }
}

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    item.value = await getRequirement(id)
    feedbacks.value = await loadRequirementFeedbackSection(id, can, listRequirementFeedbacks)
  } catch {
    failed.value = true
    item.value = null
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section v-loading="loading" class="page">
    <ErrorState v-if="failed" title="需求加载失败" description="请检查网络或确认需求是否仍可访问。" retry-label="重新加载" @retry="load" />
    <template v-if="item">
      <PageHeader :title="item.title" :eyebrow="item.requirement_no">
        <template #status>
          <StatusTag :status="item.status" :label="requirementStatusLabel[item.status]" :type="requirementStatusTagType(item.status)" />
        </template>
        <template #actions>
        <RouterLink class="back-link" :to="backTo" @click="props.embedded && emit('close')">返回列表</RouterLink>
        <el-button v-if="canEdit" @click="openEdit">编辑</el-button>
        <el-button
          v-for="action in statusActions"
          :key="action.target"
          :disabled="openingStage || (action.target === 'DONE' && !developmentReady)"
          :title="action.target === 'DONE' && !developmentReady ? '需至少一名开发人员，且全部本人确认完成；确认后刷新需求' : undefined"
          type="primary"
          plain
          @click="openStatusDialog(action)"
        >
          {{ action.label }}
        </el-button>
        </template>
      </PageHeader>

      <RequirementCollaboratorsPanel :requirement-id="item.id" :revision="item.revision" :status="item.status" @completion-ready="developmentReady = $event" @updated="emit('updated'); load()" />
      <div class="detail-grid">
      <SectionCard title="需求详情" description="范围与验收标准" class="detail-main">
        <el-descriptions :column="isMobile ? 1 : 2">
          <el-descriptions-item label="类型">
            {{ requirementTypeLabel[item.requirement_type] ?? item.requirement_type }}
          </el-descriptions-item>
          <el-descriptions-item label="优先级">{{ item.priority }}</el-descriptions-item>
          <el-descriptions-item label="需求描述" :span="isMobile ? 1 : 2">
            <div class="multiline">{{ item.description }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="验收标准" :span="isMobile ? 1 : 2">
            <div class="multiline">{{ item.acceptance_criteria || '-' }}</div>
          </el-descriptions-item>
        </el-descriptions>
      </SectionCard>
      <SectionCard title="流转信息" description="来源与版本归属" class="detail-side">
        <dl class="side-fields">
          <div><dt>来源</dt><dd>{{ item.source === 'FEEDBACK' ? '反馈转化' : '直接创建' }}</dd></div>
          <div><dt>当前版本</dt><dd><ScopedRelationLink kind="version" :id="item.current_version_id" :return-to="backTo" :parent-identity="String(item.id)" /></dd></div>
          <div><dt>更新时间</dt><dd>{{ formatLocalDateTime(item.updated_at) }}</dd></div>
        </dl>
      </SectionCard>
      </div>

      <!-- source feedbacks -->
      <SectionCard v-if="canViewFeedbacks" title="来源反馈" class="section">
        <ul v-if="feedbacks.length" class="links">
          <li v-for="f in feedbacks" :key="f.feedback_id">
            <el-link type="primary" @click="router.push(related('/feedbacks/' + f.feedback_id))">
              {{ f.feedback_no }} · {{ f.title }}
            </el-link>
            <el-tag v-if="f.is_primary" size="small" type="success" effect="light">主</el-tag>
          </li>
        </ul>
        <EmptyState v-else description="暂无可见来源反馈" compact />
      </SectionCard>
    </template>

    <!-- status dialog -->
    <el-dialog
      v-model="statusDialog"
      :title="currentAction?.label ?? '状态变更'"
      width="min(480px, 92vw)"
      :fullscreen="isMobile"
      :close-on-click-modal="false"
      :close-on-press-escape="!statusSubmitting"
      :show-close="!statusSubmitting"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item v-if="currentAction?.startsStage" :label="currentAction.target === 'DESIGNING' ? '设计人员' : '开发人员'" required>
          <RequirementAssigneeSelect v-model="stagePeople" :kind="currentAction.target === 'DESIGNING' ? 'DESIGNER' : 'DEVELOPER'" :selected="stageSelected" />
        </el-form-item>
        <el-form-item v-else-if="currentAction?.needsReason" label="原因" required>
          <el-input v-model="statusReason" type="textarea" :rows="3" />
        </el-form-item>
        <p v-if="currentAction && !currentAction.startsStage && !currentAction.needsReason">
          确认将需求状态改为「{{ requirementStatusLabel[currentAction.target] }}」？
        </p>
      </el-form>
      <template #footer>
        <el-button :disabled="statusSubmitting" @click="statusDialog = false">取消</el-button>
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
    <el-dialog v-model="editDialog" title="编辑需求" width="min(560px, 92vw)" destroy-on-close>
      <el-alert v-if="existingEditor" type="warning" :closable="false" show-icon class="presence-alert">
        <template #title>{{ existingEditor.display_name }} 正在编辑此需求</template>
        你仍可继续编辑；如数据已变化，保存时会通过 revision 冲突保护避免静默覆盖。
      </el-alert>
      <el-form label-position="top" @submit.prevent="submitEdit">
        <el-form-item label="需求类型">
          <el-select v-model="editForm.requirement_type" style="width: 100%">
            <el-option v-for="t in REQUIREMENT_TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="editForm.title" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="editForm.priority" style="width: 160px">
            <el-option v-for="p in REQUIREMENT_PRIORITIES" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="需求描述">
          <el-input v-model="editForm.description" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="验收标准">
          <el-input v-model="editForm.acceptance_criteria" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.back-link { color: var(--if-brand-500); align-self: center; }
.detail-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(250px, 300px); align-items: start; gap: var(--if-space-4); margin-top: var(--if-space-4); }
.detail-main, .detail-side { min-width: 0; }
.detail-grid > .detail-main + .detail-side { margin-top: 0; }
.detail-main :deep(.el-descriptions__content) { overflow-wrap: anywhere; }
.multiline { white-space: pre-wrap; overflow-wrap: anywhere; }
.side-fields { display: grid; gap: 13px; margin: 0; }
.side-fields > div { min-width: 0; padding-bottom: 12px; border-bottom: 1px solid var(--if-border); }
.side-fields > div:last-child { border-bottom: 0; padding-bottom: 0; }
.side-fields dt { margin-bottom: 4px; color: var(--if-text-3); font-size: 12px; }
.side-fields dd { margin: 0; font-size: 13px; overflow-wrap: anywhere; }
.section { margin-top: var(--if-space-4); }
.links { list-style: none; margin: 0; padding: 0; }
.links li { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 10px 0; border-bottom: 1px solid var(--if-border); }
.links li:last-child { border-bottom: 0; }
.presence-alert { min-width: 0; margin-bottom: var(--if-space-4); overflow-wrap: anywhere; }
.presence-alert :deep(.el-alert__content), .presence-alert :deep(.el-alert__title) { min-width: 0; overflow-wrap: anywhere; }
@media (max-width: 1199px) { .detail-grid { grid-template-columns: 1fr; } }
</style>
