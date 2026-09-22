<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { createVersion } from '@/api/versions'

const router = useRouter()
const saving = ref(false)
const form = reactive({
  version_no: '',
  name: '',
  planned_release_date: null as string | null,
  description: '',
})

async function submit(): Promise<void> {
  if (!form.version_no.trim()) {
    ElMessage.warning('请填写版本号')
    return
  }
  if (!form.name.trim()) {
    ElMessage.warning('请填写版本名称')
    return
  }
  saving.value = true
  try {
    const created = await createVersion({
      version_no: form.version_no.trim(),
      name: form.name.trim(),
      planned_release_date: form.planned_release_date || null,
      description: form.description.trim() || null,
    })
    ElMessage.success('版本已创建')
    await router.replace(`/versions/${created.id}`)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section class="page">
    <h1 class="page-title">新建版本</h1>
    <el-card shadow="never">
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="版本号" required>
          <el-input v-model="form.version_no" placeholder="如 V1.0.0" maxlength="32" />
        </el-form-item>
        <el-form-item label="版本名称" required>
          <el-input v-model="form.name" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="计划上线日期">
          <el-date-picker
            v-model="form.planned_release_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="可选"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="4" />
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
