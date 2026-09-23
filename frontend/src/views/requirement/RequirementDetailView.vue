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
const id = Number(route.params.id)

const item = ref<Requirement | null>(null)
const feedbacks = ref<LinkedFeedback[]>([])
const loading = ref(false)
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
  try {
    item.value = await getRequirement(id)
    feedbacks.value = await loadRequirementFeedbackSection(id, can, listRequirementFeedbacks)
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
    <template v-if="item">
      <div class="head">
        <div>
          <div class="no">{{ item.requirement_no }}</div>
          <h1 class="page-title">{{ item.title }}</h1>
        </div>
        <StatusTag
          :status="item.status"
          :label="requirementStatusLabel[item.status]"
          :type="requirementStatusTagType(item.status)"
        />
      </div>

      <div v-if="canEdit || statusActions.length" class="toolbar">
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
      </div>

      <el-card shadow="never">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="类型">
            {{ requirementTypeLabel[item.requirement_type] ?? item.requirement_type }}
          </el-descriptions-item>
          <el-descriptions-item label="优先级">{{ item.priority }}</el-descriptions-item>
          <el-descriptions-item label="来源">
            {{ item.source === 'FEEDBACK' ? '反馈转化' : '直接创建' }}
          </el-descriptions-item>
          <el-descriptions-item label="当前版本">{{ item.current_version_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="需求描述">
            <div class="multiline">{{ item.description }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="验收标准">
            <div class="multiline">{{ item.acceptance_criteria || '-' }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ item.updated_at }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- source feedbacks -->
      <el-card v-if="canViewFeedbacks" shadow="never" class="section">
        <div class="section-title">来源反馈</div>
        <ul v-if="feedbacks.length" class="links">
          <li v-for="f in feedbacks" :key="f.feedback_id">
            <el-link type="primary" @click="router.push('/feedbacks/' + f.feedback_id)">
              {{ f.feedback_no }} · {{ f.title }}
            </el-link>
            <el-tag v-if="f.is_primary" size="small" type="success" effect="light">主</el-tag>
          </li>
        </ul>
        <el-empty v-else :image-size="60" description="暂无可见来源反馈" />
      </el-card>
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
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
.no { font-size: 12px; color: #94a3b8; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.multiline { white-space: pre-wrap; }
.section { margin-top: 16px; }
.section-title { font-weight: 600; margin-bottom: 8px; }
.links { list-style: none; margin: 0; padding: 0; }
.links li { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
</style>
