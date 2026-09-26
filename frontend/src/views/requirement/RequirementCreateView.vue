<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { createRequirement } from '@/api/requirements'
import { REQUIREMENT_PRIORITIES, REQUIREMENT_TYPES } from '@/constants/requirement'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import type { RequirementCreatePayload } from '@/types/domain'

const router = useRouter()
const props = withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })
const emit = defineEmits<{ cancel: []; created: [id: number] }>()
const saving = ref(false)
const form = reactive({
  title: '',
  requirement_type: 'FEATURE',
  priority: 'P2' as RequirementCreatePayload['priority'],
  description: '',
  acceptance_criteria: '',
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
    ElMessage.warning('需求描述至少需要 2 个字符')
    return
  }
  saving.value = true
  try {
    const created = await createRequirement({
      title: form.title.trim(),
      requirement_type: form.requirement_type,
      priority: form.priority,
      description: form.description.trim(),
      acceptance_criteria: form.acceptance_criteria.trim() || null,
    })
    ElMessage.success('需求已创建')
    if (props.embedded) emit('created', created.id)
    else await router.replace(`/requirements/${created.id}`)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section :class="props.embedded ? 'embedded-form' : 'page'">
    <PageHeader v-if="!props.embedded" title="新建需求" description="定义要解决的问题及完成标准。" eyebrow="需求管理 / 新建" />
    <SectionCard :title="props.embedded ? undefined : '需求信息'" :description="props.embedded ? undefined : '需求也可以从反馈转化创建。'" class="editor-card">
      <el-form label-position="top" @submit.prevent="submit">
        <div class="editor-grid">
        <el-form-item label="需求类型" required>
          <el-select v-model="form.requirement_type" style="width: 100%">
            <el-option v-for="t in REQUIREMENT_TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority" style="width: 100%">
            <el-option v-for="p in REQUIREMENT_PRIORITIES" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" required class="span-2">
          <el-input v-model="form.title" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="需求描述" required class="span-2">
          <el-input v-model="form.description" type="textarea" :rows="6" />
        </el-form-item>
        <el-form-item label="验收标准" class="span-2">
          <el-input v-model="form.acceptance_criteria" type="textarea" :rows="3" />
        </el-form-item>
        </div>
        <div class="editor-actions">
          <el-button @click="cancel">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="saving">创建</el-button>
        </div>
      </el-form>
    </SectionCard>
  </section>
</template>

<style scoped>
.embedded-form { min-width: 0; }
.embedded-form :deep(.section-card) { border: 0; box-shadow: none; }
@media (max-width: 767px) { .embedded-form :deep(.editor-actions) { bottom: 0; } }
</style>
