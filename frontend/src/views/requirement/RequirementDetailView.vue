<script setup lang="ts">
import RequirementProgress from '@/components/RequirementProgress.vue'
import { computed, defineAsyncComponent, onMounted, reactive, ref, watch } from 'vue'
import RequirementNumber from '@/components/RequirementNumber.vue'
import RichTextContent from '@/components/RichTextContent.vue'
import DeleteEntityButton from '@/components/DeleteEntityButton.vue'
import { plainTextToHtml, richTextPlainText } from '@/utils/richText'
const RichTextEditor = defineAsyncComponent(() => import('@/components/RichTextEditor.vue'))
const VersionCreateView = defineAsyncComponent(() => import('@/views/version/VersionCreateView.vue'))
import { ElMessage } from 'element-plus'
import { actionErrorMessage } from '@/utils/actionError'
import { useRoute, useRouter } from 'vue-router'
import {
  changeRequirementStatus,
  getRequirement,
  listRequirementFeedbacks,
  updateRequirement,
} from '@/api/requirements'
import ScopedRelationLink from '@/components/ScopedRelationLink.vue'
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
const canEdit = computed(() => can('rd.requirement.edit') && item.value?.status !== 'ONLINE')
const canViewFeedbacks = computed(() => can('rd.feedback.view'))
const canCreateVersion = computed(() => !!item.value && !item.value.current_version_id && !['ONLINE', 'CANCELED'].includes(item.value.status) && ['rd.version.create', 'rd.version.edit', 'rd.version.view', 'rd.requirement.view'].every(permission => can(permission)))
const createVersionDialog = ref(false)
const creatingVersion = ref(false)
const refreshingVersionRequirement = ref(false)

async function refreshVersionRequirement(): Promise<void> {
  if (refreshingVersionRequirement.value) return
  refreshingVersionRequirement.value = true
  try {
    item.value = await getRequirement(id)
    emit('updated')
    if (!canCreateVersion.value) {
      createVersionDialog.value = false
      ElMessage.info('需求信息已刷新，请查看当前版本或需求状态。')
    }
  } catch (error) {
    ElMessage.error(actionErrorMessage(error))
  } finally { refreshingVersionRequirement.value = false }
}

async function onVersionCreated(): Promise<void> {
  createVersionDialog.value = false
  emit('updated')
  await load()
}

// --- status dialog ---
const statusDialog = ref(false)
const statusSubmitting = ref(false)
const currentAction = ref<ReqStatusAction | null>(null)
const statusReason = ref('')
const statusError = ref('')

function openStatusDialog(action: ReqStatusAction): void {
  currentAction.value = action
  statusReason.value = ''
  statusError.value = ''
  statusDialog.value = true
}

async function submitStatus(): Promise<void> {
  if (!item.value || !currentAction.value || statusSubmitting.value || !can('rd.requirement.status')) return
  const action = currentAction.value
  if (action.needsReason && statusReason.value.trim().length < 2) {
    ElMessage.warning('请填写原因（至少 2 个字符）')
    return
  }
  statusSubmitting.value = true; statusError.value = ''
  try {
    await changeRequirementStatus(
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
    await showConflict(error, item.value.revision, () => { statusDialog.value = false })
    statusError.value = actionErrorMessage(error)
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
let originalDescription = { text: '', format: 'PLAIN' as 'PLAIN' | 'HTML', editorHtml: '' }

function openEdit(): void {
  if (!item.value || !canEdit.value) return
  fillEditForm(item.value)
  editDialog.value = true
  void startPresence()
}

function fillEditForm(latest: Requirement): void {
  const format = latest.description_format ?? 'PLAIN'
  const editorHtml = format === 'HTML' ? latest.description : plainTextToHtml(latest.description)
  originalDescription = { text: latest.description, format, editorHtml }
  Object.assign(editForm, {
    title: latest.title,
    requirement_type: latest.requirement_type,
    priority: latest.priority,
    description: editorHtml,
    acceptance_criteria: latest.acceptance_criteria ?? '',
  })
}

watch(editDialog, (open) => {
  if (!open) void stopPresence()
})

async function submitEdit(): Promise<void> {
  if (!item.value || !canEdit.value || editSubmitting.value) return
  if (editForm.title.trim().length < 2 || richTextPlainText(editForm.description).length < 2) {
    ElMessage.warning('请填写需求标题与描述（至少 2 个字符）')
    return
  }
  editSubmitting.value = true
  try {
    const descriptionUnchanged = editForm.description === originalDescription.editorHtml
    await updateRequirement(item.value.id, {
      title: editForm.title.trim(),
      requirement_type: editForm.requirement_type,
      priority: editForm.priority,
      description: descriptionUnchanged ? originalDescription.text : editForm.description.trim(),
      description_format: descriptionUnchanged ? originalDescription.format : 'HTML',
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

function onDeleted() {
  emit('updated')
  if (props.embedded) emit('close')
  else void router.replace(backTo.value)
}

onMounted(load)
</script>

<template>
  <section v-loading="loading" class="page">
    <ErrorState v-if="failed" title="需求加载失败" description="请检查网络或确认需求是否仍可访问。" retry-label="重新加载" @retry="load" />
    <template v-if="item">

      <PageHeader :title="item.title.trim() || '未填写需求标题'">
        <template #eyebrow><RequirementNumber :number="item.requirement_no" /></template>
        <template #status>
          <StatusTag :status="item.status" :label="requirementStatusLabel[item.status]" :type="requirementStatusTagType(item.status)" />
        </template>
        <template #actions>
        <RouterLink class="back-link" :to="backTo" @click="props.embedded && emit('close')">返回列表</RouterLink>
        <el-button v-if="canEdit" @click="openEdit">编辑</el-button>
        <el-button v-if="canCreateVersion" @click="createVersionDialog = true">创建版本</el-button>
        <DeleteEntityButton v-if="canEdit && item.status === 'DRAFT' && !item.current_version_id && item.source === 'DIRECT'" kind="requirements" :id="item.id" :revision="item.revision" :title="item.title" @refresh="load" @deleted="onDeleted" />

        </template>
      </PageHeader>

      <RequirementProgress :item="item" @updated="load" @status="openStatusDialog" />
      <div class="detail-grid">
      <SectionCard title="需求详情" description="范围与验收标准" class="detail-main">
        <el-descriptions :column="isMobile ? 1 : 2">
          <el-descriptions-item label="类型">
            {{ requirementTypeLabel[item.requirement_type] ?? item.requirement_type }}
          </el-descriptions-item>
          <el-descriptions-item label="优先级">{{ item.priority }}</el-descriptions-item>
          <el-descriptions-item label="需求描述" :span="isMobile ? 1 : 2">
            <RichTextContent :requirement-id="item.id" :content="item.description" :format="item.description_format" />
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

    <el-dialog v-model="createVersionDialog" title="创建版本并关联需求" width="min(720px, calc(100vw - 24px))" append-to-body destroy-on-close :close-on-click-modal="false" :show-close="!creatingVersion" :close-on-press-escape="!creatingVersion">
      <VersionCreateView v-if="createVersionDialog && item" embedded :requirement="{ id: item.id, revision: item.revision, title: item.title }" :requirement-refreshing="refreshingVersionRequirement" @cancel="createVersionDialog = false" @created="onVersionCreated" @refresh-requirement="refreshVersionRequirement" @saving="creatingVersion = $event" />
    </el-dialog>

    <!-- status dialog -->
    <el-dialog
      v-model="statusDialog"
      :title="currentAction?.label ?? '状态变更'"
      width="min(480px, 92vw)"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item :label="currentAction?.reasonLabel || (currentAction?.needsReason ? '原因（必填）' : '原因（选填）')" :required="currentAction?.needsReason">
          <el-input v-model="statusReason" type="textarea" :rows="3" />
        </el-form-item>
        <p v-if="statusError" role="alert">{{ statusError }}</p>
      </el-form>
      <template #footer>
        <el-button @click="statusDialog = false">取消</el-button>
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
          <RichTextEditor :requirement-id="item?.id" v-model="editForm.description" :disabled="editSubmitting" label="需求描述" />
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
.detail-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(250px, 300px); align-items: start; gap: var(--if-space-4); }
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
