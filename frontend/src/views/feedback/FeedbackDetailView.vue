<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type UploadRequestOptions } from 'element-plus'
import { useRoute } from 'vue-router'
import {
  changeFeedbackStatus,
  createFeedbackComment,
  downloadFeedbackAttachment,
  getFeedback,
  listFeedbackAttachments,
  listFeedbackComments,
  updateFeedback,
  uploadFeedbackAttachment,
} from '@/api/feedbacks'
import { listSystems } from '@/api/systems'
import { usePermission } from '@/composables/usePermission'
import StatusTag from '@/components/StatusTag.vue'
import {
  FEEDBACK_TYPES,
  FEEDBACK_URGENCIES,
  availableStatusActions,
  feedbackStatusLabel,
  feedbackStatusTagType,
  feedbackTypeLabel,
  feedbackUrgencyLabel,
  type StatusAction,
} from '@/constants/feedback'
import type {
  AttachmentItem,
  BusinessModuleItem,
  BusinessSystemItem,
  CommentItem,
  Feedback,
} from '@/types/domain'

const route = useRoute()
const { can } = usePermission()
const feedbackId = Number(route.params.id)

const item = ref<Feedback | null>(null)
const loading = ref(false)
const attachments = ref<AttachmentItem[]>([])
const comments = ref<CommentItem[]>([])
const systems = ref<BusinessSystemItem[]>([])
const modules = ref<BusinessModuleItem[]>([])
const canReadSystems = computed(() => can('sys.system.view'))
const canEdit = computed(() => can('rd.feedback.edit'))
const canAttach = computed(() => can('rd.feedback.create'))

const statusActions = computed<StatusAction[]>(() =>
  item.value ? availableStatusActions(item.value.status, canEdit.value) : [],
)

// --- status change dialog ---
const statusDialog = ref(false)
const statusSubmitting = ref(false)
const currentAction = ref<StatusAction | null>(null)
const statusForm = reactive({ reason: '', duplicate_of_id: null as number | null })

function openStatusDialog(action: StatusAction): void {
  currentAction.value = action
  statusForm.reason = ''
  statusForm.duplicate_of_id = null
  statusDialog.value = true
}

async function submitStatus(): Promise<void> {
  if (!item.value || !currentAction.value) return
  const action = currentAction.value
  if (action.needsReason && !statusForm.reason.trim()) {
    ElMessage.warning('请填写原因')
    return
  }
  if (action.needsDuplicate && !statusForm.duplicate_of_id) {
    ElMessage.warning('请填写重复目标反馈 ID')
    return
  }
  statusSubmitting.value = true
  try {
    await changeFeedbackStatus(item.value.id, {
      status: action.target,
      revision: item.value.revision,
      reason: statusForm.reason.trim() || null,
      duplicate_of_id: action.needsDuplicate ? statusForm.duplicate_of_id : null,
    })
    ElMessage.success('状态已更新')
    statusDialog.value = false
  } catch {
    // 409 / 422 surfaced by the global interceptor; reload to refresh revision.
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
  feedback_type: '',
  urgency: '',
  system_id: null as number | null,
  module_id: null as number | null,
  description: '',
  expected_result: '',
  actual_result: '',
  reproduce_steps: '',
})
const editModuleOptions = computed(() =>
  editForm.system_id ? modules.value.filter((m) => m.system_id === editForm.system_id) : [],
)

function openEdit(): void {
  if (!item.value) return
  Object.assign(editForm, {
    title: item.value.title,
    feedback_type: item.value.feedback_type,
    urgency: item.value.urgency,
    system_id: item.value.system_id ?? null,
    module_id: item.value.module_id ?? null,
    description: item.value.description,
    expected_result: item.value.expected_result ?? '',
    actual_result: item.value.actual_result ?? '',
    reproduce_steps: item.value.reproduce_steps ?? '',
  })
  editDialog.value = true
}

function onEditSystemChange(): void {
  editForm.module_id = null
}

async function submitEdit(): Promise<void> {
  if (!item.value) return
  editSubmitting.value = true
  try {
    await updateFeedback(item.value.id, {
      title: editForm.title.trim(),
      feedback_type: editForm.feedback_type,
      urgency: editForm.urgency,
      system_id: editForm.system_id ?? null,
      module_id: editForm.module_id ?? null,
      description: editForm.description.trim(),
      expected_result: editForm.expected_result.trim() || null,
      actual_result: editForm.actual_result.trim() || null,
      reproduce_steps: editForm.reproduce_steps.trim() || null,
      revision: item.value.revision,
    })
    ElMessage.success('反馈已更新')
    editDialog.value = false
  } catch {
    // Conflict / validation surfaced globally; reload to show latest revision.
  } finally {
    editSubmitting.value = false
    await load()
  }
}

// --- attachments ---
async function uploadAttachment(options: UploadRequestOptions): Promise<void> {
  await uploadFeedbackAttachment(feedbackId, options.file as File)
  ElMessage.success('附件已上传')
  attachments.value = await listFeedbackAttachments(feedbackId)
}

async function download(att: AttachmentItem): Promise<void> {
  const blob = await downloadFeedbackAttachment(feedbackId, att.file_id)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = att.original_name
  a.click()
  URL.revokeObjectURL(url)
}

// --- comments ---
const commentText = ref('')
const commentSubmitting = ref(false)

async function submitComment(): Promise<void> {
  if (!commentText.value.trim()) return
  commentSubmitting.value = true
  try {
    await createFeedbackComment(feedbackId, commentText.value.trim())
    commentText.value = ''
    comments.value = await listFeedbackComments(feedbackId)
  } finally {
    commentSubmitting.value = false
  }
}

function systemName(id: number | null | undefined): string {
  if (!id) return '-'
  return systems.value.find((s) => s.id === id)?.name ?? `#${id}`
}

function moduleName(id: number | null | undefined): string {
  if (!id) return '-'
  return modules.value.find((m) => m.id === id)?.name ?? `#${id}`
}

async function load(): Promise<void> {
  loading.value = true
  try {
    item.value = await getFeedback(feedbackId)
    attachments.value = await listFeedbackAttachments(feedbackId)
    comments.value = await listFeedbackComments(feedbackId)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (canReadSystems.value) {
    try {
      const data = await listSystems()
      systems.value = data.systems
      modules.value = data.modules
    } catch {
      // Optional display enrichment.
    }
  }
  await load()
})
</script>

<template>
  <section v-loading="loading" class="page">
    <template v-if="item">
      <div class="head">
        <div>
          <div class="no">{{ item.feedback_no }}</div>
          <h1 class="page-title">{{ item.title }}</h1>
        </div>
        <StatusTag
          :status="item.status"
          :label="feedbackStatusLabel[item.status]"
          :type="feedbackStatusTagType(item.status)"
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
            {{ feedbackTypeLabel[item.feedback_type] ?? item.feedback_type }}
          </el-descriptions-item>
          <el-descriptions-item label="紧急程度">
            {{ feedbackUrgencyLabel[item.urgency] ?? item.urgency }}
          </el-descriptions-item>
          <el-descriptions-item label="所属系统">{{ systemName(item.system_id) }}</el-descriptions-item>
          <el-descriptions-item label="所属模块">{{ moduleName(item.module_id) }}</el-descriptions-item>
          <el-descriptions-item label="详细描述">
            <div class="multiline">{{ item.description }}</div>
          </el-descriptions-item>
          <el-descriptions-item v-if="item.expected_result" label="期望结果">
            <div class="multiline">{{ item.expected_result }}</div>
          </el-descriptions-item>
          <el-descriptions-item v-if="item.actual_result" label="实际结果">
            <div class="multiline">{{ item.actual_result }}</div>
          </el-descriptions-item>
          <el-descriptions-item v-if="item.reproduce_steps" label="复现步骤">
            <div class="multiline">{{ item.reproduce_steps }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="关联需求">{{ item.main_requirement_id || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="item.duplicate_of_id" label="重复于">
            #{{ item.duplicate_of_id }}
          </el-descriptions-item>
          <el-descriptions-item label="提交人">#{{ item.submitter_id }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ item.created_at }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ item.updated_at }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- attachments -->
      <el-card shadow="never" class="section">
        <div class="section-head">
          <span class="section-title">附件</span>
          <el-upload
            v-if="canAttach"
            :show-file-list="false"
            :http-request="uploadAttachment"
          >
            <el-button size="small">上传附件</el-button>
          </el-upload>
        </div>
        <ul v-if="attachments.length" class="attachments">
          <li v-for="a in attachments" :key="a.file_id">
            <el-link type="primary" @click="download(a)">{{ a.original_name }}</el-link>
            <span class="att-size">{{ Math.max(1, Math.round(a.size / 1024)) }} KB</span>
          </li>
        </ul>
        <el-empty v-else :image-size="60" description="暂无附件" />
      </el-card>

      <!-- comments -->
      <el-card shadow="never" class="section">
        <div class="section-title">评论</div>
        <ul v-if="comments.length" class="comments">
          <li v-for="c in comments" :key="c.id">
            <div class="comment-meta">#{{ c.created_by }} · {{ c.created_at }}</div>
            <div class="multiline">{{ c.content }}</div>
          </li>
        </ul>
        <el-empty v-else :image-size="60" description="暂无评论" />
        <div class="comment-form">
          <el-input v-model="commentText" type="textarea" :rows="2" placeholder="写下评论…" />
          <el-button
            type="primary"
            :loading="commentSubmitting"
            :disabled="!commentText.trim()"
            @click="submitComment"
          >
            发表
          </el-button>
        </div>
      </el-card>
    </template>

    <!-- status change dialog -->
    <el-dialog
      v-model="statusDialog"
      :title="currentAction?.label ?? '状态变更'"
      width="min(480px, 92vw)"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item v-if="currentAction?.needsDuplicate" label="重复目标反馈 ID" required>
          <el-input-number v-model="statusForm.duplicate_of_id" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="原因" :required="currentAction?.needsReason">
          <el-input v-model="statusForm.reason" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="statusDialog = false">取消</el-button>
        <el-button type="primary" :loading="statusSubmitting" @click="submitStatus">确定</el-button>
      </template>
    </el-dialog>

    <!-- edit dialog -->
    <el-dialog v-model="editDialog" title="编辑反馈" width="min(560px, 92vw)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="submitEdit">
        <el-form-item label="反馈类型">
          <el-select v-model="editForm.feedback_type" style="width: 100%">
            <el-option v-for="t in FEEDBACK_TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="editForm.title" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="紧急程度">
          <el-radio-group v-model="editForm.urgency">
            <el-radio v-for="u in FEEDBACK_URGENCIES" :key="u.value" :value="u.value">
              {{ u.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="canReadSystems">
          <el-form-item label="所属系统">
            <el-select
              v-model="editForm.system_id"
              clearable
              placeholder="可选"
              style="width: 100%"
              @change="onEditSystemChange"
            >
              <el-option v-for="s in systems" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="editForm.system_id" label="所属模块">
            <el-select v-model="editForm.module_id" clearable placeholder="可选" style="width: 100%">
              <el-option v-for="m in editModuleOptions" :key="m.id" :label="m.name" :value="m.id" />
            </el-select>
          </el-form-item>
        </template>
        <el-form-item label="详细描述">
          <el-input v-model="editForm.description" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="期望结果">
          <el-input v-model="editForm.expected_result" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="实际结果">
          <el-input v-model="editForm.actual_result" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="复现步骤">
          <el-input v-model="editForm.reproduce_steps" type="textarea" :rows="3" />
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
.section-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.section-title { font-weight: 600; }
.attachments, .comments { list-style: none; margin: 0; padding: 0; }
.attachments li { display: flex; align-items: center; gap: 10px; padding: 6px 0; }
.att-size { color: #94a3b8; font-size: 12px; }
.comments li { padding: 8px 0; border-bottom: 1px solid #f1f5f9; }
.comment-meta { color: #94a3b8; font-size: 12px; margin-bottom: 2px; }
.comment-form { display: flex; gap: 8px; align-items: flex-start; margin-top: 12px; }
.comment-form .el-button { flex-shrink: 0; }
</style>
