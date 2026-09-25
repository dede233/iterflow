<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  changeRequirementStatus,
  getRequirement,
  listRequirementFeedbacks,
  updateRequirement,
} from '@/api/requirements'
import { editingHeartbeat, endEditing, startEditing } from '@/api/editing'
import { usePermission } from '@/composables/usePermission'
import {
  canStartRequirementEditing,
  loadRequirementFeedbackSection,
} from '@/security/detailAuthorization'
import StatusTag from '@/components/StatusTag.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import { useResponsive } from '@/composables/useResponsive'
import { formatLocalDateTime } from '@/utils/dates'
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

const route = useRoute()
const router = useRouter()
const { can } = usePermission()
const { isMobile } = useResponsive()
const id = Number(route.params.id)

const item = ref<Requirement | null>(null)
const feedbacks = ref<LinkedFeedback[]>([])
const loading = ref(false)
const failed = ref(false)
const canEdit = computed(() => can('rd.requirement.edit'))
const canChangeStatus = computed(() => can('rd.requirement.status'))
const canViewFeedbacks = computed(() => can('rd.feedback.view'))
const statusActions = computed<ReqStatusAction[]>(() =>
  item.value ? availableRequirementStatusActions(item.value.status, canChangeStatus.value) : [],
)

let timer: ReturnType<typeof setInterval> | undefined
let editingStarted = false

// --- status dialog ---
const statusDialog = ref(false)
const statusSubmitting = ref(false)
const currentAction = ref<ReqStatusAction | null>(null)
const statusReason = ref('')

function openStatusDialog(action: ReqStatusAction): void {
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
    await changeRequirementStatus(
      item.value.id,
      action.target,
      item.value.revision,
      statusReason.value.trim() || null,
    )
    ElMessage.success('状态已更新')
    statusDialog.value = false
  } catch {
    // 409 / 422 surfaced globally; reload to refresh revision.
  } finally {
    statusSubmitting.value = false
    await load()
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
  if (!item.value) return
  Object.assign(editForm, {
    title: item.value.title,
    requirement_type: item.value.requirement_type,
    priority: item.value.priority,
    description: item.value.description,
    acceptance_criteria: item.value.acceptance_criteria ?? '',
  })
  editDialog.value = true
}

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
    ElMessage.success('需求已更新')
    editDialog.value = false
  } catch {
    // Conflict / validation surfaced globally.
  } finally {
    editSubmitting.value = false
    await load()
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

onMounted(async () => {
  await load()
  if (!canStartRequirementEditing(can)) return
  try {
    await startEditing('REQUIREMENT', id)
    editingStarted = true
    timer = setInterval(() => editingHeartbeat('REQUIREMENT', id), 120000)
  } catch {
    // Editing hint is best-effort only.
  }
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
  if (editingStarted) void endEditing('REQUIREMENT', id)
})
</script>

<template>
  <section v-loading="loading" class="page">
    <ErrorState v-if="failed" title="需求加载失败" description="请检查网络或确认需求是否仍可访问。" retry-label="重新加载" @retry="load" />
    <template v-if="item">
      <PageHeader :title="item.title" :eyebrow="item.requirement_no">
        <template #status>
          <StatusTag :status="item.status" :label="requirementStatusLabel[item.status]" :type="requirementStatusTagType(item.status)" />
        </template>
        <template v-if="canEdit || statusActions.length" #actions>
        <el-button v-if="canEdit" @click="openEdit">编辑</el-button>
        <el-button
          v-for="action in statusActions"
          :key="action.target"
          type="primary"
          plain
          @click="openStatusDialog(action)"
        >
          {{ action.label }}
        </el-button>
        </template>
      </PageHeader>

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
          <div><dt>当前版本</dt><dd>{{ item.current_version_id || '-' }}</dd></div>
          <div><dt>更新时间</dt><dd>{{ formatLocalDateTime(item.updated_at) }}</dd></div>
        </dl>
      </SectionCard>
      </div>

      <!-- source feedbacks -->
      <SectionCard v-if="canViewFeedbacks" title="来源反馈" class="section">
        <ul v-if="feedbacks.length" class="links">
          <li v-for="f in feedbacks" :key="f.feedback_id">
            <el-link type="primary" @click="router.push('/feedbacks/' + f.feedback_id)">
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
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="原因" :required="currentAction?.needsReason">
          <el-input v-model="statusReason" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="statusDialog = false">取消</el-button>
        <el-button type="primary" :loading="statusSubmitting" @click="submitStatus">确定</el-button>
      </template>
    </el-dialog>

    <!-- edit dialog -->
    <el-dialog v-model="editDialog" title="编辑需求" width="min(560px, 92vw)" destroy-on-close>
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
.detail-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(250px, 300px); align-items: start; gap: var(--if-space-4); }
.detail-main, .detail-side { min-width: 0; }
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
@media (max-width: 1199px) { .detail-grid { grid-template-columns: 1fr; } }
</style>
