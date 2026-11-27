<script setup lang="ts">
import BusinessSystemSelect from '@/components/BusinessSystemSelect.vue'
import PeopleSelector from '@/components/PeopleSelector.vue'
import type { Participant, Person } from '@/api/collaboration'
import { computed, defineAsyncComponent, nextTick, reactive, ref, watch } from 'vue'
import { plainTextToHtml, richTextPlainText } from '@/utils/richText'
const RichTextEditor = defineAsyncComponent(() => import('@/components/RichTextEditor.vue'))
import { ElMessage } from 'element-plus'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import { createRequirement } from '@/api/requirements'
import { REQUIREMENT_PRIORITIES, REQUIREMENT_TYPES } from '@/constants/requirement'
import { actionErrorMessage } from '@/utils/actionError'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import type { Feedback, RequirementCreatePayload } from '@/types/domain'

type FeedbackConversion = {
  source: Pick<Feedback, 'id' | 'title' | 'description' | 'description_format' | 'system_id' | 'system_name'>
  confirmPeople: Person[]
  allowed: boolean
  error: string
  submitLabel?: string
  isDirty?: () => boolean
  busy?: boolean
  validate?: () => boolean
  submit: (payload: RequirementCreatePayload) => Promise<number | undefined>
}

const router = useRouter()
const props = withDefaults(defineProps<{ embedded?: boolean; conversion?: FeedbackConversion }>(), { embedded: false })
const emit = defineEmits<{ cancel: []; created: [id: number]; saving: [value: boolean]; expanded: [value: boolean] }>()
const saving = ref(false)
const expanded = ref(false)
const completed = ref(false)
const formRoot = ref<HTMLElement>()
const errors = reactive({ title: '', description: '', confirm: '' })
const submitError = ref('')
const roles = reactive<Record<Participant['role'], number[]>>({
  CONFIRM: props.conversion?.confirmPeople.map(person => person.id) ?? [],
  DESIGN: [],
  DEVELOP: [],
  ACCEPT: [],
})
const deliveryRoles: Participant['role'][] = ['DESIGN', 'DEVELOP', 'ACCEPT']
const roleLabels = { CONFIRM: '需求确认人', DESIGN: '设计人员（可选）', DEVELOP: '开发人员', ACCEPT: '验收人员' }
const developerOptions = reactive(new Map<number, Person>())
const acceptanceOptions = computed(() => [...developerOptions.values()].filter(person => roles.ACCEPT.includes(person.id)))
const developersToAdd = computed(() => roles.DEVELOP.filter(id => !roles.ACCEPT.includes(id)))
const includesPrefilledConfirmer = computed(() => props.conversion?.confirmPeople.some(person => roles.CONFIRM.includes(person.id)))
const sourceFeedback = props.conversion?.source
const form = reactive({
  system_id: null as number | null,
  title: sourceFeedback?.title ?? '',
  requirement_type: 'FEATURE',
  priority: 'P2' as RequirementCreatePayload['priority'],
  description: sourceFeedback
    ? (sourceFeedback.description_format === 'HTML' ? sourceFeedback.description : plainTextToHtml(sourceFeedback.description))
    : '',
  acceptance_criteria: '',
})
const inheritedSystemId = computed(() => props.conversion?.source.system_id ?? null)
const systemSelectionConflicts = computed(() =>
  inheritedSystemId.value != null && form.system_id != null && form.system_id !== inheritedSystemId.value,
)

const initialSnapshot = JSON.stringify({ form, roles })
const draft = useUnsavedChanges({
  active: () => !completed.value,
  isDirty: () => JSON.stringify({ form, roles }) !== initialSnapshot || !!props.conversion?.isDirty?.(),
  isBusy: () => saving.value || !!props.conversion?.busy,
})
const requestClose = (confirmClean = props.embedded) => draft.requestLeave(confirmClean)
defineExpose({ requestClose })
onBeforeRouteLeave(() => draft.requestLeave())
watch(saving, value => emit('saving', value), { flush: 'sync' })
function toggleExpanded(): void { expanded.value = !expanded.value; emit('expanded', expanded.value) }

function rememberDevelopers(role: Participant['role'], people: Person[]) {
  if (role === 'DEVELOP') people.forEach(person => developerOptions.set(person.id, person))
}
function addDevelopersToAcceptance() {
  if (saving.value || props.conversion?.busy || !developersToAdd.value.length) return
  roles.ACCEPT = [...new Set([...roles.ACCEPT, ...developersToAdd.value])]
}

function validationMessage(field: keyof typeof errors): string {
  if (field === 'title') return form.title.trim().length < 2 ? '标题至少需要 2 个字符' : ''
  if (field === 'description') return richTextPlainText(form.description).trim().length < 2 ? '需求描述至少需要 2 个字符' : ''
  return roles.CONFIRM.length === 0 ? '请至少选择一名需求确认人' : ''
}
watch(() => form.title, () => { if (errors.title) errors.title = validationMessage('title') })
watch(() => form.description, () => { if (errors.description) errors.description = validationMessage('description') })
watch(() => roles.CONFIRM, () => { if (errors.confirm) errors.confirm = validationMessage('confirm') })
async function cancel(): Promise<void> {
  if (saving.value) return
  if (props.embedded) { if (await requestClose()) emit('cancel') }
  else router.back()
}

async function submit(): Promise<void> {
  const conversion = props.conversion
  if (saving.value || systemSelectionConflicts.value || (conversion && !conversion.allowed)) return
  submitError.value = ''
  errors.title = validationMessage('title')
  errors.description = validationMessage('description')
  errors.confirm = validationMessage('confirm')
  const firstError = (['title', 'description', 'confirm'] as const).find(field => errors[field])
  if (firstError) {
    await nextTick()
    const field = formRoot.value?.querySelector<HTMLElement>(`[data-field="${firstError}"] input:not([type="file"]), [data-field="${firstError}"] [contenteditable="true"]`)
    field?.focus()
    field?.scrollIntoView?.({ block: 'nearest' })
    return
  }
  if (conversion?.validate && !conversion.validate()) return
  saving.value = true
  try {
    const payload: RequirementCreatePayload = {
      participants: Object.entries(roles).flatMap(([role, ids]) => ids.map(user_id => ({ role: role as Participant['role'], user_id }))),
      system_id: form.system_id,
      title: form.title.trim(),
      requirement_type: form.requirement_type,
      priority: form.priority,
      description: form.description.trim(),
      description_format: 'HTML',
      acceptance_criteria: form.acceptance_criteria.trim() || null,
    }
    const id = conversion
      ? await conversion.submit(payload)
      : (await createRequirement(payload)).id
    if (id === undefined) return
    completed.value = true
    if (!conversion) ElMessage.success('需求已创建')
    if (props.embedded) emit('created', id)
    else await router.replace(`/requirements/${id}`)
  } catch (error) {
    submitError.value = actionErrorMessage(error)
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
          <RichTextEditor v-model="form.description" :feedback-id="conversion?.source.id" :disabled="saving" label="需求描述" />
        </el-form-item>
        <el-form-item label="验收标准" class="span-2">
          <el-input v-model="form.acceptance_criteria" type="textarea" :rows="3" />
        </el-form-item>
        <div class="span-2 form-section-heading">归属与确认</div>
        <el-form-item label="业务系统">
          <div v-if="inheritedSystemId != null" class="inherited-system">
            <span>{{ conversion?.source.system_name || `系统 #${inheritedSystemId}` }}</span>
            <template v-if="systemSelectionConflicts">
              <p class="system-conflict" role="alert">反馈的业务系统已更新，与草稿中的选择不同。</p>
              <el-button link type="primary" :disabled="saving" @click="form.system_id = null">使用反馈的业务系统</el-button>
            </template>
          </div>
          <BusinessSystemSelect v-else v-model="form.system_id" />
        </el-form-item>
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
        <el-form-item label="需求确认人" required data-field="confirm" :error="errors.confirm">
          <PeopleSelector v-model="roles.CONFIRM" kind="requirement" :selected="conversion?.confirmPeople" :aria-invalid="!!errors.confirm" multiple />
          <p class="people-hint">{{ includesPrefilledConfirmer ? '默认选择当前账号，可修改。' : '' }}可以选择多人，由任意一名有权限的确认人确认即可。</p>
        </el-form-item>
        <details class="span-2 optional-people"><summary>后续人员安排 <span>可在创建后、确认需求前补齐</span></summary><div class="editor-grid">
          <el-form-item v-for="role in deliveryRoles" :key="role" :label="roleLabels[role]" :data-role="role">
            <PeopleSelector v-model="roles[role]" kind="requirement" :selected="role === 'ACCEPT' ? acceptanceOptions : undefined" multiple @people-added="rememberDevelopers(role, $event)" />
            <el-button v-if="role === 'ACCEPT'" class="acceptance-copy" link type="primary" native-type="button" :disabled="saving || conversion?.busy || !developersToAdd.length" @click="addDevelopersToAcceptance">将开发人员加入验收</el-button>
          </el-form-item>
        </div><p class="people-hint">确认需求前须指定开发和验收人员。设计人员选填，同一人可承担多个角色。</p></details>
        <slot name="additional-fields" />
        </div>
        </div>
        <p v-if="conversion?.error || submitError" class="submit-error" role="alert">{{ conversion?.error || submitError }}</p>
        <div class="editor-actions">
          <el-button :disabled="saving" @click="cancel">取消</el-button>
          <el-button type="primary" native-type="submit" :disabled="systemSelectionConflicts || (conversion && !conversion.allowed)" :loading="saving">{{ conversion?.submitLabel ?? '创建' }}</el-button>
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
.people-hint { margin: 4px 0 0; color: var(--if-text-secondary); font-size: var(--if-font-caption); line-height: 1.5; }
.acceptance-copy { min-height: 32px; }
.embedded-form { min-width: 0; }
.embedded-form :deep(.section-card) { border: 0; box-shadow: none; }
.expand-writing { margin-left: auto; }
.inherited-system { overflow-wrap: anywhere; }
.system-conflict { margin: 0; color: var(--if-danger-fg); }
[data-field="description"] :deep(.el-form-item__label) { width: 100%; display: flex; align-items: center; }
.writing-expanded :deep(.rich-text-editor .tiptap) { min-height: min(48dvh, 480px); max-height: 64dvh; }
.submit-error { margin: 0; padding: 8px 20px; color: var(--if-danger-fg); overflow-wrap: anywhere; }
@media (max-width: 767px) {
  .embedded-form :deep(.editor-actions) { bottom: 0; }
  .acceptance-copy { min-height: 44px; }
}
</style>
