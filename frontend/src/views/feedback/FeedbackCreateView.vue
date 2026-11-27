<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import type { UploadFile, UploadUserFile } from 'element-plus'
import { createFeedback, uploadFeedbackAttachment } from '@/api/feedbacks'
import { createOnlineReviewFeedback } from '@/api/requirements'
import { listSystems } from '@/api/systems'
import { usePermission } from '@/composables/usePermission'
import { FEEDBACK_TYPES, FEEDBACK_URGENCIES } from '@/constants/feedback'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import PeopleSelector from '@/components/PeopleSelector.vue'
import type { BusinessSystemItem, FeedbackCreatePayload } from '@/types/domain'
import { isRevisionConflict } from '@/types/revisionConflict'
import { actionErrorMessage } from '@/utils/actionError'
import { richTextPlainText } from '@/utils/richText'

const RichTextEditor = defineAsyncComponent(() => import('@/components/RichTextEditor.vue'))

const router = useRouter()
const props = withDefaults(defineProps<{
  embedded?: boolean
  onlineReview?: { id: number; number: string; title: string; revision: number; refreshRevision: () => Promise<number> }
}>(), { embedded: false })
const emit = defineEmits<{ cancel: []; created: [id: number]; recorded: []; saving: [value: boolean] }>()
const { can } = usePermission()
const saving = ref(false)
const refreshing = ref(false)
const busy = computed(() => saving.value || refreshing.value)
const completed = ref(false)
const createdId = ref<number | null>(null)
const submitError = ref('')
const needsRefresh = ref(false)
const sourceRevision = ref(props.onlineReview?.revision ?? 0)
const systems = ref<BusinessSystemItem[]>([])
const canReadSystems = computed(() => can(['sys.system.view', 'sys.system.manage']))
const fileList = ref<UploadUserFile[]>([])
const recipientIds = ref<number[]>([])

const form = reactive({
  title: '',
  feedback_type: 'SYSTEM_ISSUE' as (typeof FEEDBACK_TYPES)[number]['value'],
  urgency: 'NORMAL' as (typeof FEEDBACK_URGENCIES)[number]['value'],
  system_id: null as number | null,
  description: '',
  reproduce_steps: '',
})

const initialSnapshot = JSON.stringify(form)
const draft = useUnsavedChanges({
  active: () => !completed.value,
  isDirty: () => fileList.value.length > 0 || (createdId.value === null && (JSON.stringify(form) !== initialSnapshot || recipientIds.value.length > 0)),
  isBusy: () => busy.value,
})
const requestClose = () => draft.requestLeave(props.embedded)
defineExpose({ requestClose })
if (!props.onlineReview) onBeforeRouteLeave(() => draft.requestLeave())
watch(busy, value => emit('saving', value), { flush: 'sync' })

async function cancel(): Promise<void> {
  if (busy.value) return
  if (props.embedded) { if (await requestClose()) emit('cancel') }
  else router.back()
}

async function refreshRequirement(): Promise<void> {
  if (!props.onlineReview || busy.value) return
  refreshing.value = true
  try {
    sourceRevision.value = await props.onlineReview.refreshRevision()
    submitError.value = ''
    needsRefresh.value = false
  } catch {
    submitError.value = '暂时无法刷新需求信息，已保留你的输入。'
  } finally {
    refreshing.value = false
  }
}

async function submit(): Promise<void> {
  if (busy.value || completed.value || needsRefresh.value) return
  let id = createdId.value
  if (id === null) {
    if (form.title.trim().length < 2) {
      ElMessage.warning('标题至少需要 2 个字符')
      return
    }
    if (Array.from(richTextPlainText(form.description)).length < 2) {
      ElMessage.warning('详细描述至少需要 2 个字符')
      return
    }
    if (!recipientIds.value.length) {
      ElMessage.warning('请选择至少一位反馈接收人')
      return
    }
  }
  saving.value = true
  submitError.value = ''
  try {
    if (id === null) {
      const payload = {
        title: form.title.trim(),
        feedback_type: form.feedback_type,
        urgency: form.urgency,
        system_id: form.system_id ?? null,
        description: form.description.trim(),
        description_format: 'HTML',
        recipient_ids: recipientIds.value,
        reproduce_steps: form.reproduce_steps.trim() || null,
      } satisfies FeedbackCreatePayload
      const created = props.onlineReview
        ? await createOnlineReviewFeedback(props.onlineReview.id, { ...payload, revision: sourceRevision.value })
        : await createFeedback(payload)
      id = created.id
      createdId.value = id
      emit('recorded')
    }
    for (const item of [...fileList.value]) {
      const raw = (item as UploadFile).raw
      if (raw) await uploadFeedbackAttachment(id, raw)
      fileList.value = fileList.value.filter(file => file.uid !== item.uid)
    }
    completed.value = true
  } catch (error) {
    if (id !== null) {
      submitError.value = '反馈已提交。可重试上传剩余附件，或移除上传失败的文件。'
    } else if (props.onlineReview && isRevisionConflict(error)) {
      needsRefresh.value = true
      submitError.value = '需求信息已更新。请刷新需求信息后重新提交，已保留你的输入。'
    } else {
      submitError.value = actionErrorMessage(error)
    }
    return
  } finally {
    saving.value = false
  }
  ElMessage.success('反馈已提交')
  if (props.embedded) emit('created', id)
  else await router.replace(`/feedbacks/${id}`)
}

onMounted(async () => {
  if (canReadSystems.value) {
    try {
      const data = await listSystems()
      systems.value = data.systems
    } catch {
      // Optional; feedback can be submitted without a system.
    }
  }
})
</script>

<template>
  <section :class="props.embedded ? 'embedded-form' : 'page'">
    <PageHeader v-if="!props.embedded" title="提交反馈" description="说明你遇到的问题或希望改进的体验，便于团队跟进。" eyebrow="反馈中心 / 新建" />
    <SectionCard :title="props.embedded ? undefined : '反馈内容'" :description="props.embedded ? undefined : '描述遇到的问题，再选择归属和接收人。'" class="form-card">
      <el-form label-position="top" :disabled="busy" @submit.prevent="submit">
        <div class="create-form-fields">
        <div v-if="props.onlineReview" class="source-requirement">
          <span>来源需求</span><strong>{{ props.onlineReview.number }} · {{ props.onlineReview.title }}</strong>
        </div>
        <template v-if="createdId === null">
        <el-form-item label="标题" required class="span-2">
          <el-input v-model="form.title" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="详细描述" required>
          <RichTextEditor v-model="form.description" :disabled="busy" label="详细描述" />
        </el-form-item>
        <div class="form-grid">
        <el-form-item label="反馈类型" required>
          <el-select v-model="form.feedback_type" style="width: 100%">
            <el-option v-for="t in FEEDBACK_TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="紧急程度">
          <el-radio-group v-model="form.urgency">
            <el-radio v-for="u in FEEDBACK_URGENCIES" :key="u.value" :value="u.value">
              {{ u.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="canReadSystems">
          <el-form-item label="所属系统" class="span-2">
            <el-select
              v-model="form.system_id"
              clearable
              placeholder="可选"
              style="width: 100%"
            >
              <el-option v-for="s in systems" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
          </el-form-item>
        </template>
        </div>
        <h2 class="form-subtitle">接收人与补充信息</h2>
        <el-form-item label="反馈接收人" required><PeopleSelector v-model="recipientIds" kind="feedback" multiple /></el-form-item>
        <el-form-item label="复现步骤">
          <el-input v-model="form.reproduce_steps" type="textarea" :rows="3" />
        </el-form-item>
        </template>
        <el-form-item label="附件">
          <el-upload
            v-model:file-list="fileList"
            :auto-upload="false"
            :limit="9"
            :disabled="busy"
            multiple
          >
            <template #trigger><el-button v-if="createdId === null">选择文件</el-button></template>
            <template #tip>
              <div v-if="createdId === null" class="upload-tip">提交后自动上传；支持图片 / PDF / 文本 / Office 文档，单文件 ≤ 50MB。</div>
            </template>
          </el-upload>
        </el-form-item>
        </div>
        <div v-if="submitError" class="submit-error">
          <p role="alert">{{ submitError }}</p>
          <el-button v-if="needsRefresh" type="primary" plain :loading="refreshing" @click="refreshRequirement">刷新需求信息</el-button>
        </div>
        <div class="actions form-actions">
          <el-button :disabled="busy" @click="cancel">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="saving" :disabled="needsRefresh || refreshing">
            {{ createdId === null ? '提交' : (fileList.length ? '重试上传' : '完成') }}
          </el-button>
        </div>
      </el-form>
    </SectionCard>
  </section>
</template>

<style scoped>
.form-card { max-width: 940px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 24px; }
.span-2 { grid-column: 1 / -1; }
.form-subtitle { margin: 4px 0 18px; padding-top: 20px; border-top: 1px solid var(--if-border); font-size: 14px; font-weight: 700; }
.actions { position: sticky; bottom: 0; z-index: 8; background: var(--if-bg-surface); padding-bottom: 12px; display: flex; justify-content: flex-end; gap: 8px; padding-top: 16px; border-top: 1px solid var(--if-border); }
.upload-tip { color: var(--if-text-3); font-size: 12px; line-height: 1.5; }
.source-requirement { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; margin: 0 0 20px; padding: 12px; background: var(--if-bg-subtle); border-radius: var(--if-radius-sm); overflow-wrap: anywhere; }
.source-requirement span { color: var(--if-text-2); font-size: var(--if-font-caption); }
.source-requirement strong { min-width: 0; font-size: var(--if-font-body); font-weight: 600; }
.submit-error { margin-bottom: 16px; }
.submit-error p { margin: 0 0 8px; color: var(--el-color-danger); overflow-wrap: anywhere; }
.embedded-form .submit-error { flex: 0 0 auto; margin: 0; padding: 12px 20px; border-top: 1px solid var(--if-border); }
.embedded-form { min-width: 0; }
.embedded-form :deep(.section-card) { border: 0; box-shadow: none; }
@media (max-width: 767px) { .form-grid { grid-template-columns: 1fr; } .span-2 { grid-column: auto; } .form-actions { position: sticky; bottom: calc(var(--if-bottom-nav-height) + env(safe-area-inset-bottom)); z-index: 8; padding: 12px 0; background: var(--if-bg-surface); } .embedded-form .form-actions { bottom: 0; } .form-actions .el-button { flex: 1; margin: 0; } }
</style>
