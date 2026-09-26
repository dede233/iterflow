<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { createVersion } from '@/api/versions'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'

const router = useRouter()
const props = withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })
const emit = defineEmits<{ cancel: []; created: [id: number] }>()
const saving = ref(false)
const form = reactive({
  version_no: '',
  name: '',
  planned_release_date: null as string | null,
  description: '',
})

function cancel(): void {
  if (props.embedded) emit('cancel')
  else router.back()
}

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
    if (props.embedded) emit('created', created.id)
    else await router.replace(`/versions/${created.id}`)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section :class="props.embedded ? 'embedded-form' : 'page'">
    <PageHeader v-if="!props.embedded" title="新建版本" description="设置版本标识与计划上线日期。" eyebrow="版本管理 / 新建" />
    <SectionCard :title="props.embedded ? undefined : '版本信息'" :description="props.embedded ? undefined : '创建后可在版本详情中管理需求清单。'" class="editor-card">
      <el-form label-position="top" @submit.prevent="submit">
        <div class="editor-grid">
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
        <el-form-item label="说明" class="span-2">
          <el-input v-model="form.description" type="textarea" :rows="4" />
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
