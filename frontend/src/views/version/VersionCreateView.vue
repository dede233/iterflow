<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { createVersion } from '@/api/versions'
import { usePermission } from '@/composables/usePermission'
import { useAuthStore } from '@/stores/auth'
import { actionErrorMessage } from '@/utils/actionError'
import { isRevisionConflict } from '@/types/revisionConflict'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'

const router = useRouter()
const props = withDefaults(defineProps<{
  embedded?: boolean
  requirement?: { id: number; revision: number; title: string }
  requirementRefreshing?: boolean
}>(), { embedded: false, requirementRefreshing: false })
const emit = defineEmits<{ cancel: []; created: [id: number]; refreshRequirement: []; saving: [value: boolean] }>()
const { can } = usePermission()
const auth = useAuthStore()
const saving = ref(false)
const versionNoError = ref('')
const submitError = ref('')
const requirementConflict = ref(false)
const allowed = computed(() => can('rd.version.create') && (!props.requirement || ['rd.version.edit', 'rd.version.view', 'rd.requirement.view'].every(permission => can(permission))))
let active = true
onBeforeUnmount(() => { active = false })
const form = reactive({
  version_no: '',
  name: props.requirement ? Array.from(props.requirement.title.trim() || `需求 #${props.requirement.id}`).slice(0, 100).join('') : '',
  planned_release_date: null as string | null,
  description: '',
})
watch(() => form.version_no, () => { versionNoError.value = '' })
watch(() => props.requirement?.revision, (revision, previous) => {
  if (revision !== previous && requirementConflict.value) {
    requirementConflict.value = false
    submitError.value = ''
  }
})

function cancel(): void {
  if (saving.value) return
  if (props.embedded) emit('cancel')
  else router.back()
}

async function submit(): Promise<void> {
  if (saving.value || props.requirementRefreshing || !allowed.value) return
  if (!form.version_no.trim()) {
    ElMessage.warning('请填写版本号')
    return
  }
  if (!form.name.trim()) {
    ElMessage.warning('请填写版本名称')
    return
  }
  saving.value = true
  emit('saving', true)
  versionNoError.value = ''; submitError.value = ''; requirementConflict.value = false
  const session = `${auth.user?.id}:${auth.accessToken}`
  try {
    const created = await createVersion({
      version_no: form.version_no.trim(),
      name: form.name.trim(),
      planned_release_date: form.planned_release_date || null,
      description: form.description.trim() || null,
      ...(props.requirement ? { requirement_id: props.requirement.id, requirement_revision: props.requirement.revision } : {}),
    })
    if (!active || session !== `${auth.user?.id}:${auth.accessToken}`) return
    ElMessage.success(props.requirement ? '版本已创建并关联当前需求' : '版本已创建')
    if (props.embedded) emit('created', created.id)
    else await router.replace(`/versions/${created.id}`)
  } catch (error) {
    if (!active || session !== `${auth.user?.id}:${auth.accessToken}`) return
    const response = (error as { response?: { status?: number; data?: { code?: number; data?: { field?: string; reason?: string } } } })?.response
    if (response?.status === 409 && response.data?.code === 40934 && response.data.data?.field === 'version_no' && response.data.data?.reason === 'duplicate') {
      versionNoError.value = actionErrorMessage(error)
    } else if (props.requirement && isRevisionConflict(error)) {
      requirementConflict.value = true
      submitError.value = '需求已被其他用户修改，请先刷新需求，再确认并提交。已填写的版本信息会保留。'
    } else submitError.value = actionErrorMessage(error)
  } finally {
    saving.value = false
    emit('saving', false)
  }
}
</script>

<template>
  <section :class="props.embedded ? 'embedded-form' : 'page'">
    <PageHeader v-if="!props.embedded" title="新建版本" description="设置版本标识与计划上线日期。" eyebrow="版本管理 / 新建" />
    <SectionCard :title="props.embedded ? undefined : '版本信息'" :description="props.embedded ? undefined : '创建后可在版本详情中管理需求清单。'" class="editor-card">
      <p v-if="props.requirement" class="requirement-context">创建后将当前需求加入新版本，之后可在版本详情查看进度并发布。</p>
      <el-form label-position="top" :disabled="saving || props.requirementRefreshing" @submit.prevent="submit">
        <div class="editor-grid">
        <el-form-item label="版本号" required :error="versionNoError">
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
        <p v-if="submitError" class="submit-error" role="alert">{{ submitError }}</p>
        <el-button v-if="requirementConflict" :loading="props.requirementRefreshing" :disabled="saving" @click="emit('refreshRequirement')">刷新需求</el-button>
        <div class="editor-actions">
          <el-button :disabled="saving" @click="cancel">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="saving" :disabled="!allowed || props.requirementRefreshing">{{ props.requirement ? '创建并关联' : '创建' }}</el-button>
        </div>
      </el-form>
    </SectionCard>
  </section>
</template>

<style scoped>
.embedded-form { min-width: 0; }
.embedded-form :deep(.section-card) { border: 0; box-shadow: none; }
.requirement-context { margin: 0 0 16px; color: var(--if-text-2); font-size: 13px; line-height: 1.6; }
.submit-error { color: var(--el-color-danger); overflow-wrap: anywhere; }
@media (max-width: 767px) { .embedded-form :deep(.editor-actions) { bottom: 0; } }
</style>
