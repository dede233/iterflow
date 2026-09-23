<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { createRequirement } from '@/api/requirements'
import { REQUIREMENT_PRIORITIES, REQUIREMENT_TYPES } from '@/constants/requirement'
import type { RequirementCreatePayload } from '@/types/domain'

const router = useRouter()
const saving = ref(false)
const form = reactive({
  title: '',
  requirement_type: 'FEATURE',
  priority: 'P2' as RequirementCreatePayload['priority'],
  description: '',
  acceptance_criteria: '',
})

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
    await router.replace(`/requirements/${created.id}`)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section class="page">
    <h1 class="page-title">新建需求</h1>
    <el-card shadow="never">
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="需求类型" required>
          <el-select v-model="form.requirement_type" style="width: 100%">
            <el-option v-for="t in REQUIREMENT_TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model="form.title" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority" style="width: 160px">
            <el-option v-for="p in REQUIREMENT_PRIORITIES" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="需求描述" required>
          <el-input v-model="form.description" type="textarea" :rows="6" />
        </el-form-item>
        <el-form-item label="验收标准">
          <el-input v-model="form.acceptance_criteria" type="textarea" :rows="3" />
        </el-form-item>
        <div class="actions">
          <el-button @click="router.back()">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="saving">创建</el-button>
        </div>
      </el-form>
    </el-card>
  </section>
</template>

<style scoped>
.actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
