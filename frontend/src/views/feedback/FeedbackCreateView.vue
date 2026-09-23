<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import type { UploadFile, UploadUserFile } from 'element-plus'
import { createFeedback, uploadFeedbackAttachment } from '@/api/feedbacks'
import { listSystems } from '@/api/systems'
import { usePermission } from '@/composables/usePermission'
import { FEEDBACK_TYPES, FEEDBACK_URGENCIES } from '@/constants/feedback'
import type { BusinessModuleItem, BusinessSystemItem } from '@/types/domain'

const router = useRouter()
const { can } = usePermission()
const saving = ref(false)
const systems = ref<BusinessSystemItem[]>([])
const modules = ref<BusinessModuleItem[]>([])
const canReadSystems = computed(() => can('sys.system.view'))
const fileList = ref<UploadUserFile[]>([])

const form = reactive({
  title: '',
  feedback_type: 'SYSTEM_ISSUE' as (typeof FEEDBACK_TYPES)[number]['value'],
  urgency: 'NORMAL' as (typeof FEEDBACK_URGENCIES)[number]['value'],
  system_id: null as number | null,
  module_id: null as number | null,
  description: '',
  expected_result: '',
  actual_result: '',
  reproduce_steps: '',
})

const moduleOptions = computed(() =>
  form.system_id ? modules.value.filter((m) => m.system_id === form.system_id) : [],
)

function onSystemChange(): void {
  form.module_id = null
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
  try {
    const created = await createFeedback({
      title: form.title.trim(),
      feedback_type: form.feedback_type,
      urgency: form.urgency,
      system_id: form.system_id ?? null,
      module_id: form.module_id ?? null,
      description: form.description.trim(),
      expected_result: form.expected_result.trim() || null,
      actual_result: form.actual_result.trim() || null,
      reproduce_steps: form.reproduce_steps.trim() || null,
    })
    // Upload any staged attachments against the new feedback id.
    for (const item of fileList.value) {
      const raw = (item as UploadFile).raw
      if (raw) await uploadFeedbackAttachment(created.id, raw as File)
    }
    ElMessage.success('反馈已提交')
    await router.replace(`/feedbacks/${created.id}`)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  if (canReadSystems.value) {
    try {
      const data = await listSystems()
      systems.value = data.systems
      modules.value = data.modules
    } catch {
      // Optional; feedback can be submitted without system/module.
    }
  }
})
</script>

<template>
  <section class="page">
    <h1 class="page-title">提交反馈</h1>
    <el-card shadow="never">
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="反馈类型" required>
          <el-select v-model="form.feedback_type" style="width: 100%">
            <el-option v-for="t in FEEDBACK_TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model="form.title" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="紧急程度">
          <el-radio-group v-model="form.urgency">
            <el-radio v-for="u in FEEDBACK_URGENCIES" :key="u.value" :value="u.value">
              {{ u.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="canReadSystems">
          <el-form-item label="所属系统">
            <el-select
              v-model="form.system_id"
              clearable
              placeholder="可选"
              style="width: 100%"
              @change="onSystemChange"
            >
              <el-option v-for="s in systems" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="form.system_id" label="所属模块">
            <el-select v-model="form.module_id" clearable placeholder="可选" style="width: 100%">
              <el-option v-for="m in moduleOptions" :key="m.id" :label="m.name" :value="m.id" />
            </el-select>
          </el-form-item>
        </template>
        <el-form-item label="详细描述" required>
          <el-input v-model="form.description" type="textarea" :rows="6" />
        </el-form-item>
        <el-form-item label="期望结果">
          <el-input v-model="form.expected_result" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="实际结果">
          <el-input v-model="form.actual_result" type="textarea" :rows="2" />
        </el-form-item>
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
        <div class="actions">
          <el-button @click="router.back()">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="saving">提交</el-button>
        </div>
      </el-form>
    </el-card>
  </section>
</template>

<style scoped>
.actions { display: flex; justify-content: flex-end; gap: 8px; }
.upload-tip { color: #94a3b8; font-size: 12px; line-height: 1.5; }
</style>
