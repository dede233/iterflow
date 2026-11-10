<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import type { UploadFile, UploadUserFile } from 'element-plus'
import { createFeedback, uploadFeedbackAttachment } from '@/api/feedbacks'
import { listSystems } from '@/api/systems'
import { usePermission } from '@/composables/usePermission'
import { FEEDBACK_TYPES, FEEDBACK_URGENCIES } from '@/constants/feedback'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import PeopleSelector from '@/components/PeopleSelector.vue'
import type { BusinessSystemItem } from '@/types/domain'

const router = useRouter()
const props = withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })
const emit = defineEmits<{ cancel: []; created: [id: number] }>()
const { can } = usePermission()
const saving = ref(false)
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

function cancel(): void {
  if (props.embedded) emit('cancel')
  else router.back()
}

async function submit(): Promise<void> {
  if (form.title.trim().length < 2) {
    ElMessage.warning('标题至少需要 2 个字符')
    return
  }
  if (form.description.trim().length < 2) {
    ElMessage.warning('详细描述至少需要 2 个字符')
    return
  }
  saving.value = true
  if (!recipientIds.value.length) {
    ElMessage.warning('请选择至少一位反馈接收人')
    saving.value = false
    return
  }
  try {
    const created = await createFeedback({
      title: form.title.trim(),
      feedback_type: form.feedback_type,
      urgency: form.urgency,
      system_id: form.system_id ?? null,
      description: form.description.trim(),
      recipient_ids: recipientIds.value,
      reproduce_steps: form.reproduce_steps.trim() || null,
    })
    // Upload any staged attachments against the new feedback id.
    for (const item of fileList.value) {
      const raw = (item as UploadFile).raw
      if (raw) await uploadFeedbackAttachment(created.id, raw as File)
    }
    ElMessage.success('反馈已提交')
    if (props.embedded) emit('created', created.id)
    else await router.replace(`/feedbacks/${created.id}`)
  } finally {
    saving.value = false
  }
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
      <el-form label-position="top" @submit.prevent="submit">
        <div class="create-form-fields">
        <el-form-item label="标题" required class="span-2">
          <el-input v-model="form.title" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="详细描述" required>
          <el-input v-model="form.description" type="textarea" :rows="6" />
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
        <el-form-item label="附件">
          <el-upload
            v-model:file-list="fileList"
            :auto-upload="false"
            :limit="9"
            multiple
          >
            <el-button>选择文件</el-button>
            <template #tip>
              <div class="upload-tip">提交后自动上传；支持图片 / PDF / 文本 / Office 文档，单文件 ≤ 50MB。</div>
            </template>
          </el-upload>
        </el-form-item>
        </div>
        <div class="actions form-actions">
          <el-button @click="cancel">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="saving">提交</el-button>
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
.embedded-form { min-width: 0; }
.embedded-form :deep(.section-card) { border: 0; box-shadow: none; }
@media (max-width: 767px) { .form-grid { grid-template-columns: 1fr; } .span-2 { grid-column: auto; } .form-actions { position: sticky; bottom: calc(var(--if-bottom-nav-height) + env(safe-area-inset-bottom)); z-index: 8; padding: 12px 0; background: var(--if-bg-surface); } .embedded-form .form-actions { bottom: 0; } .form-actions .el-button { flex: 1; margin: 0; } }
</style>
