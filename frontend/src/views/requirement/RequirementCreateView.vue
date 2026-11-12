<script setup lang="ts">
import BusinessSystemSelect from '@/components/BusinessSystemSelect.vue'
import PeopleSelector from '@/components/PeopleSelector.vue'
import type { Participant } from '@/api/collaboration'
import { defineAsyncComponent, nextTick, reactive, ref, watch } from 'vue'
import { richTextPlainText } from '@/utils/richText'
const RichTextEditor = defineAsyncComponent(() => import('@/components/RichTextEditor.vue'))
import { ElMessage } from 'element-plus'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import { createRequirement } from '@/api/requirements'
import { REQUIREMENT_PRIORITIES, REQUIREMENT_TYPES } from '@/constants/requirement'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import type { RequirementCreatePayload } from '@/types/domain'

const router = useRouter()
const props = withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })
const emit = defineEmits<{ cancel: []; created: [id: number]; saving: [value: boolean]; expanded: [value: boolean] }>()
const saving = ref(false)
const expanded = ref(false)
const completed = ref(false)
const formRoot = ref<HTMLElement>()
const errors = reactive({ title: '', description: '' })
const roles = reactive<Record<Participant['role'], number[]>>({ CONFIRM: [], DESIGN: [], DEVELOP: [], ACCEPT: [] })
const deliveryRoles: Participant['role'][] = ['DESIGN', 'DEVELOP', 'ACCEPT']
const roleLabels = { CONFIRM: '需求确认人', DESIGN: '设计人员（可选）', DEVELOP: '开发人员', ACCEPT: '验收人员' }
const form = reactive({
  system_id: null as number | null,
  title: '',
  requirement_type: 'FEATURE',
  priority: 'P2' as RequirementCreatePayload['priority'],
  description: '',
  acceptance_criteria: '',
})

const initialSnapshot = JSON.stringify({ form, roles })
const draft = useUnsavedChanges({
  active: () => !completed.value,
  isDirty: () => JSON.stringify({ form, roles }) !== initialSnapshot,
  isBusy: () => saving.value,
})
const requestClose = draft.requestLeave
defineExpose({ requestClose })
onBeforeRouteLeave(() => draft.requestLeave())
watch(saving, value => emit('saving', value), { flush: 'sync' })
function toggleExpanded(): void { expanded.value = !expanded.value; emit('expanded', expanded.value) }

function validationMessage(field: keyof typeof errors): string {
  return field === 'title'
    ? (form.title.trim().length < 2 ? '标题至少需要 2 个字符' : '')
    : (richTextPlainText(form.description).trim().length < 2 ? '需求描述至少需要 2 个字符' : '')
}
watch(() => form.title, () => { if (errors.title) errors.title = validationMessage('title') })
watch(() => form.description, () => { if (errors.description) errors.description = validationMessage('description') })
async function cancel(): Promise<void> {
  if (saving.value) return
  if (props.embedded) { if (await requestClose()) emit('cancel') }
  else router.back()
}

async function submit(): Promise<void> {
  if (saving.value) return
  errors.title = validationMessage('title')
  errors.description = validationMessage('description')
  const firstError = errors.title ? 'title' : errors.description ? 'description' : null
  if (firstError) {
    await nextTick()
    const field = formRoot.value?.querySelector<HTMLElement>(`[data-field="${firstError}"] input:not([type="file"]), [data-field="${firstError}"] [contenteditable="true"]`)
    field?.focus()
    field?.scrollIntoView?.({ block: 'nearest' })
    return
  }
  saving.value = true
  try {
    const created = await createRequirement({
      participants: Object.entries(roles).flatMap(([role, ids]) => ids.map(user_id => ({ role: role as Participant['role'], user_id }))),
      system_id: form.system_id,
      title: form.title.trim(),
      requirement_type: form.requirement_type,
      priority: form.priority,
      description: form.description.trim(),
      description_format: 'HTML',
      acceptance_criteria: form.acceptance_criteria.trim() || null,
    })
    completed.value = true
    ElMessage.success('需求已创建')
    if (props.embedded) emit('created', created.id)
    else await router.replace(`/requirements/${created.id}`)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section ref="formRoot" :class="[props.embedded ? 'embedded-form' : 'page', { 'writing-expanded': expanded }]">
    <PageHeader v-if="!props.embedded" title="新建需求" description="定义要解决的问题及完成标准。" eyebrow="需求管理 / 新建" />
    <SectionCard :title="props.embedded ? undefined : '需求信息'" :description="props.embedded ? undefined : '需求也可以从反馈转化创建。'" class="editor-card">
      <el-form label-position="top" :disabled="saving" @submit.prevent="submit">
        <div class="create-form-fields">
        <div class="editor-grid">
        <el-form-item label="标题" required class="span-2" data-field="title" :error="errors.title">
          <el-input v-model="form.title" maxlength="200" show-word-limit :aria-invalid="!!errors.title" />
        </el-form-item>
        <el-form-item label="需求描述" required class="span-2" data-field="description" :error="errors.description">
          <template #label><span>需求描述</span><el-button class="expand-writing" link :disabled="saving" @click="toggleExpanded">{{ expanded ? '收起编辑' : (props.embedded ? '全屏编辑' : '展开编辑') }}</el-button></template>
          <RichTextEditor v-model="form.description" :disabled="saving" label="需求描述" />
        </el-form-item>
        <el-form-item label="验收标准" class="span-2">
          <el-input v-model="form.acceptance_criteria" type="textarea" :rows="3" />
        </el-form-item>
        <div class="span-2 form-section-heading">归属与确认</div>
        <el-form-item label="业务系统"><BusinessSystemSelect v-model="form.system_id" /></el-form-item>
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
        <el-form-item label="需求确认人"><PeopleSelector v-model="roles.CONFIRM" kind="requirement" multiple /></el-form-item>
        <details class="span-2 optional-people"><summary>后续人员安排 <span>可在待开发阶段设置</span></summary><div class="editor-grid">
          <el-form-item v-for="role in deliveryRoles" :key="role" :label="roleLabels[role]"><PeopleSelector v-model="roles[role]" kind="requirement" multiple /></el-form-item>
        </div></details>
        </div>
        </div>
        <div class="editor-actions">
          <el-button :disabled="saving" @click="cancel">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="saving">创建</el-button>
        </div>
      </el-form>
    </SectionCard>
  </section>
</template>

<style scoped>
.form-section-heading { margin: 4px 0 20px; padding-top: 20px; border-top: 1px solid var(--if-border); font-size: var(--if-font-body); font-weight: 600; }
.optional-people { border-top: 1px solid var(--if-border); padding: 12px 0; margin-bottom: 12px; }
.optional-people summary { cursor: pointer; padding: 8px 0; font-weight: 500; }
.optional-people summary span { color: var(--if-text-tertiary); font-size: var(--if-font-caption); font-weight: 400; margin-left: 8px; }
.optional-people .editor-grid { margin-top: 12px; }
.embedded-form { min-width: 0; }
.embedded-form :deep(.section-card) { border: 0; box-shadow: none; }
.expand-writing { margin-left: auto; }
[data-field="description"] :deep(.el-form-item__label) { width: 100%; display: flex; align-items: center; }
.writing-expanded :deep(.rich-text-editor .tiptap) { min-height: min(48dvh, 480px); max-height: 64dvh; }
@media (max-width: 767px) { .embedded-form :deep(.editor-actions) { bottom: 0; } }
</style>
