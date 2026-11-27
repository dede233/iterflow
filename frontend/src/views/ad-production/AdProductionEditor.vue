<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, reactive, ref, shallowRef } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  createAdProduction, getAdProduction, listAdProductionDesigners, updateAdProduction, updateAdProductionStatus,
  type AdProduction, type AdProductionDesignerOption, type AdProductionUpdateFields,
} from '@/api/adProductions'
import RevisionConflictDialog from '@/components/RevisionConflictDialog.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import { useRevisionConflict } from '@/composables/useRevisionConflict'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import { AD_PRODUCTION_IMAGE_TYPES, AD_PRODUCTION_LABELS, AD_PRODUCTION_PUBLISHER_LABEL, AD_PRODUCTION_STATUSES, MERCHANT_AD_STATUSES, adProductionStatusDisplay, type AdProductionKind, type AdProductionStatus } from '@/constants/adProduction'
import { actionErrorMessage } from '@/utils/actionError'
import { formatLocalDateTime } from '@/utils/dates'
import { editorImageEntries } from '@/utils/requirementImages'
import { plainTextToHtml, richTextPlainText } from '@/utils/richText'
import AdProductionImage from './AdProductionImage.vue'
import { adProductionText, adProductionTitle, designerName, publisherName } from './adProductionDisplay'

const RichTextEditor = defineAsyncComponent(() => import('@/components/RichTextEditor.vue'))

const designerFields = [
  { key: 'receiver_id', label: '需求接收人' },
  { key: 'completed_by_id', label: '实际完成人' },
] as const
type DesignerField = typeof designerFields[number]['key']
type EditableFields = {
  title: string
  content: string
  processing_result: string
  due: Date | null
  status: AdProductionStatus
} & Record<DesignerField, number | null>

const props = defineProps<{ kind: AdProductionKind; record: AdProduction | null; mobile: boolean; statusOnly?: boolean }>()
const emit = defineEmits<{ saved: [record: AdProduction]; reloaded: [record: AdProduction] }>()
const visible = defineModel<boolean>({ required: true })
const labels = computed(() => AD_PRODUCTION_LABELS[props.kind])
const isMerchantAd = computed(() => props.kind === 'MERCHANT_AD')
const statusOptions = computed(() => isMerchantAd.value ? MERCHANT_AD_STATUSES : AD_PRODUCTION_STATUSES)

const MIB = 1024 * 1024
const IMAGE_LIMIT = 5
const IMAGE_SIZE_LIMIT = 5 * MIB
const UPLOAD_SIZE_LIMIT = 15 * MIB

const current = shallowRef(props.record)

function editableFields(record: AdProduction | null): EditableFields {
  return {
    title: record?.title ?? '',
    content: record ? (record.content_format === 'HTML' ? record.content : plainTextToHtml(record.content)) : '',
    processing_result: record?.processing_result ?? '',
    due: record?.due_at ? new Date(record.due_at) : null,
    status: record?.status ?? 'NOT_STARTED',
    receiver_id: record?.receiver_id ?? null,
    completed_by_id: record?.completed_by_id ?? null,
  }
}

const initial = reactive(editableFields(current.value))
const form = reactive<EditableFields>({ ...initial })
const formRef = ref<FormInstance>()
const fileInput = ref<HTMLInputElement>()
const saving = ref(false)
const saveError = ref('')
const imageError = ref('')
const statusMenuOpen = ref(false)
const designerMenusOpen = reactive({ receiver_id: false, completed_by_id: false })
const designerOptions = shallowRef<AdProductionDesignerOption[]>([])
const designersState = ref<'loading' | 'ready' | 'error'>('loading')
const designerRequest = new AbortController()
const visibleDesignerFields = computed(() => designerFields.filter(({ key }) =>
  key === 'receiver_id' ? !props.statusOnly : form.status === 'COMPLETED',
))
const staged = shallowRef<{ key: number; file: File }[]>([])
const removalIds = ref<number[]>([])
const keptImages = computed(() => current.value?.images.filter(image => !removalIds.value.includes(image.file_id)) ?? [])
const removedImages = computed(() => current.value?.images.filter(image => removalIds.value.includes(image.file_id)) ?? [])
const imageCount = computed(() => keptImages.value.length + staged.value.length)
let nextImageKey = 0
let disposed = false
let completionSelected = false
let completedByChanged = false

const rules: FormRules<EditableFields> = {
  title: [{
    validator: (_rule, value: string, done) => {
      if (current.value && !current.value.title && value === initial.title) return done()
      const title = value.trim()
      const hasText = title.replace(/[\p{Cc}\p{Cf}]/gu, '').trim().length > 0
      done(!hasText || title.includes('\0') || Array.from(title).length > 200 ? new Error('标题须填写 1–200 字') : undefined)
    },
    trigger: 'blur',
  }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
  receiver_id: [{
    validator: (_rule, value: number | null, done) => {
      done(!current.value && value == null ? new Error('请选择需求接收人') : undefined)
    },
    trigger: 'change',
  }],
  completed_by_id: [{
    validator: (_rule, value: number | null, done) => {
      done(isMerchantAd.value && form.status === 'COMPLETED' && value === null ? new Error('请选择实际完成人') : undefined)
    },
    trigger: 'change',
  }],
  processing_result: [{
    validator: (_rule, value: string, done) => {
      const text = value.trim()
      const hasText = /[^\s\p{Cc}\p{Cf}\p{Mn}\p{Me}]/u.test(text)
      done(!hasText || text.includes('\0') || Array.from(text).length > 4000 ? new Error('处理结果须填写 1–4000 字') : undefined)
    },
    trigger: ['blur', 'change'],
  }],
  content: [{
    required: true,
    validator: (_rule, value: string, done) => {
      if (current.value && value === initial.content) return done()
      const length = Array.from(richTextPlainText(value)).length
      done(length < 1 || length > 3000 ? new Error('需求内容须填写 1–3000 字') : undefined)
    },
    trigger: 'blur',
  }],
}

const conflict = useRevisionConflict()
const deadlineChanged = computed(() => form.due?.getTime() !== initial.due?.getTime())
const statusChanged = computed(() => form.status !== initial.status ||
  (form.status === 'COMPLETED' && (form.completed_by_id !== initial.completed_by_id ||
    form.processing_result !== initial.processing_result)))
const unsaved = useUnsavedChanges({
  isDirty: () => staged.value.length > 0 || removalIds.value.length > 0 ||
    form.title !== initial.title || form.content !== initial.content || deadlineChanged.value ||
    form.receiver_id !== initial.receiver_id || form.processing_result !== initial.processing_result || statusChanged.value,
  isBusy: () => saving.value,
})

onBeforeRouteLeave(() => unsaved.requestLeave())
onMounted(loadDesigners)
onBeforeUnmount(() => {
  disposed = true
  designerRequest.abort()
  conflict.close()
})

async function beforeClose(done: () => void): Promise<void> {
  if (!conflict.visible && await unsaved.requestLeave(!props.statusOnly)) done()
}

function cancel(): void {
  void beforeClose(() => { visible.value = false })
}

function onSelectEscape(event: KeyboardEvent, menuOpen: boolean): void {
  // ElSelect consumes Escape even when its menu is closed.
  if (menuOpen) return
  event.preventDefault()
  event.stopPropagation()
  cancel()
}

function availableDesigners(field: DesignerField): (AdProductionDesignerOption & { disabled?: boolean })[] {
  const record = current.value
  const id = record?.[field]
  if (!record || id == null || designerOptions.value.some(person => person.id === id)) return designerOptions.value
  const name = designerName(record, field)
  return [...designerOptions.value, {
    id, display_name: designersState.value === 'ready' ? `${name}（原记录）` : name, disabled: true,
  }]
}

function fillDefaultCompleter(): void {
  const designer = designerOptions.value.length === 1 ? designerOptions.value[0] : undefined
  if (designer && completionSelected && !completedByChanged && form.completed_by_id === null) {
    form.completed_by_id = designer.id
  }
}

async function loadDesigners(): Promise<void> {
  designersState.value = 'loading'
  try {
    const options = await listAdProductionDesigners(props.kind, designerRequest.signal)
    if (disposed) return
    designerOptions.value = options
    designersState.value = 'ready'
    if (options.length === 1 && !current.value && form.receiver_id === null) {
      form.receiver_id = initial.receiver_id = options[0].id
    }
    fillDefaultCompleter()
  } catch {
    if (!disposed) designersState.value = 'error'
  }
}

function onStatusChange(status: EditableFields['status']): void {
  completionSelected = status === 'COMPLETED'
  fillDefaultCompleter()
}

function onDesignerChange(field: DesignerField): void {
  if (field === 'completed_by_id') completedByChanged = true
}

function submittedDesigner(field: DesignerField): number | undefined {
  const id = form[field]
  if (!current.value) return id ?? undefined
  return id === initial[field] ? undefined : id ?? 0
}

function submittedProcessingResult(): string | undefined {
  if (!isMerchantAd.value || form.status !== 'COMPLETED' || form.processing_result === initial.processing_result) return
  return form.processing_result.trim()
}

function stageImages(event: Event): void {
  const input = event.target as HTMLInputElement
  const selected = Array.from(input.files ?? [])
  input.value = ''
  if (!selected.length || saving.value) return

  imageError.value = ''
  if (imageCount.value + selected.length > IMAGE_LIMIT) {
    imageError.value = '每条记录最多保留 5 张图片。'
    return
  }
  const invalid = selected.find(file => !AD_PRODUCTION_IMAGE_TYPES.includes(file.type) || !file.size || file.size > IMAGE_SIZE_LIMIT)
  if (invalid) {
    imageError.value = `无法添加「${invalid.name}」。请选择 5 MiB 以内的 PNG、JPEG 或 WebP 图片。`
    return
  }
  const total = [...staged.value.map(image => image.file), ...selected].reduce((size, file) => size + file.size, 0)
  if (total > UPLOAD_SIZE_LIMIT) {
    imageError.value = '本次新增图片合计须在 15 MiB 以内。'
    return
  }
  staged.value = [...staged.value, ...selected.map(file => ({ key: nextImageKey++, file }))]
}

function removeStaged(key: number): void {
  staged.value = staged.value.filter(image => image.key !== key)
  imageError.value = ''
}

function removeStored(fileId: number): void {
  removalIds.value = [...removalIds.value, fileId]
  imageError.value = ''
}

function restoreStored(fileId: number): void {
  if (imageCount.value >= IMAGE_LIMIT) return
  removalIds.value = removalIds.value.filter(id => id !== fileId)
  imageError.value = ''
}

async function saveDetails(record: AdProduction | null): Promise<AdProduction | undefined> {
  const originalContent = record && form.content === initial.content
  const contentFields: Pick<AdProductionUpdateFields, 'content' | 'content_format'> = {
    content: originalContent ? record.content : form.content.trim(),
    content_format: originalContent ? (record.content_format ?? 'PLAIN') : 'HTML',
  }
  const files = staged.value.map(image => image.file)
  let contentImages: [string, File][]
  try {
    contentImages = contentFields.content_format === 'HTML' ? editorImageEntries(contentFields.content) : []
  } catch (error) {
    saveError.value = error instanceof Error ? error.message : '无法读取正文图片，请重新插入后再试。'
    return
  }
  const uploadBytes = [...files, ...contentImages.map(([, image]) => image)].reduce((size, file) => size + file.size, 0)
  if (uploadBytes > UPLOAD_SIZE_LIMIT) {
    saveError.value = '本次新增的正文图片和图片附件合计须在 15 MiB 以内。'
    return
  }
  const title = form.title.trim()
  if (!record) {
    if (form.receiver_id === null) return
    return createAdProduction({
      ...contentFields, kind: props.kind, title, receiver_id: form.receiver_id, due_at: form.due?.toISOString(),
    }, files, contentImages)
  }
  return updateAdProduction(record.id, {
    ...contentFields,
    work_date: record.work_date,
    issuer: record.issuer,
    title: form.title !== initial.title ? title : undefined,
    status: form.status,
    due_at: deadlineChanged.value ? form.due?.toISOString() : undefined,
    clear_due_at: deadlineChanged.value && !form.due ? true : undefined,
    receiver_id: submittedDesigner('receiver_id'),
    completed_by_id: form.status === 'COMPLETED' ? submittedDesigner('completed_by_id') : undefined,
    processing_result: submittedProcessingResult(),
  }, record.revision, files, removalIds.value, contentImages)
}

async function save(): Promise<void> {
  if (saving.value || conflict.visible || !formRef.value || (props.statusOnly && !statusChanged.value)) return
  saving.value = true
  saveError.value = ''
  const record = current.value
  try {
    if (!await formRef.value.validate().catch(() => false)) return
    const saved = record && props.statusOnly
      ? await updateAdProductionStatus(record.id, {
        revision: record.revision,
        status: form.status,
        completed_by_id: form.status === 'COMPLETED' ? submittedDesigner('completed_by_id') : undefined,
        processing_result: submittedProcessingResult(),
      })
      : await saveDetails(record)
    if (!saved || disposed) return
    ElMessage.success(props.statusOnly ? '已更新状态' : record ? '已保存修改' : `已发布${labels.value.name}需求`)
    emit('saved', saved)
  } catch (error) {
    if (disposed) return
    if (record && await conflict.show(error, record.revision, {
      entityLabel: `${labels.value.name}记录`,
      getLatest: () => getAdProduction(record.id),
      summarize: latest => [
        { label: '标题', value: adProductionTitle(latest) },
        { label: AD_PRODUCTION_PUBLISHER_LABEL, value: publisherName(latest) },
        { label: '发布时间', value: formatLocalDateTime(latest.created_at) },
        { label: '截止时间', value: formatLocalDateTime(latest.due_at) },
        { label: '状态', value: adProductionStatusDisplay(props.kind, latest.status).label },
        ...designerFields.map(({ key, label }) => ({ label, value: designerName(latest, key) })),
        { label: '需求内容', value: adProductionText(latest) },
        ...(isMerchantAd.value && latest.processing_result ? [{ label: '处理结果', value: latest.processing_result }] : []),
        { label: '图片', value: latest.images.map(image => image.original_name).join('、') },
      ],
      apply: async latest => {
        try {
          await ElMessageBox.confirm('重新加载将放弃本次修改。', '重新加载服务器版本？', {
            confirmButtonText: '放弃修改并重新加载', cancelButtonText: '继续编辑', type: 'warning',
            closeOnClickModal: false, closeOnPressEscape: false, closeOnHashChange: false,
          })
        } catch { return }
        if (disposed) return
        current.value = latest
        Object.assign(initial, editableFields(latest))
        Object.assign(form, initial)
        completionSelected = false
        completedByChanged = false
        staged.value = []
        removalIds.value = []
        imageError.value = ''
        saveError.value = ''
        formRef.value?.clearValidate()
        if (props.statusOnly) emit('reloaded', latest)
      },
    })) {
      if (!disposed) saveError.value = '记录已更新。请核对最新记录，当前输入已保留。'
      return
    }
    saveError.value = actionErrorMessage(error)
  } finally {
    if (!disposed) saving.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    class="create-dialog"
    append-to-body
    destroy-on-close
    :title="statusOnly ? '更改状态' : `${record ? '编辑' : '发布'}${labels.name}需求`"
    :fullscreen="mobile && !statusOnly"
    :align-center="statusOnly"
    :before-close="beforeClose"
    :close-on-click-modal="false"
    :close-on-press-escape="!saving && !conflict.visible"
    :show-close="!saving && !conflict.visible"
    :width="statusOnly ? 'min(460px, calc(100vw - 32px))' : 'min(680px, calc(100vw - 32px))'"
  >
    <section class="embedded-form">
      <SectionCard class="editor-card">
        <el-form ref="formRef" data-testid="ad-production-editor" class="ad-form" :model="form" :rules="rules" :disabled="saving" label-position="top" scroll-to-error @submit.prevent="save">
          <div class="create-form-fields">
            <el-alert v-if="saveError" class="save-error" :title="saveError" type="error" :closable="false" show-icon />
            <h2 v-if="statusOnly && current" class="status-record-title">{{ adProductionTitle(current) }}</h2>
            <dl v-if="current" class="editor-context editor-grid">
              <div><dt>{{ AD_PRODUCTION_PUBLISHER_LABEL }}</dt><dd>{{ publisherName(current) }}</dd></div>
              <div><dt>发布时间</dt><dd><time :datetime="current.created_at">{{ formatLocalDateTime(current.created_at) }}</time></dd></div>
            </dl>
            <el-form-item v-if="!statusOnly" label="标题" prop="title" for="ad-production-title" :required="!current || !!current.title">
              <el-input id="ad-production-title" v-model="form.title" placeholder="请输入标题" />
            </el-form-item>
            <div v-if="visibleDesignerFields.length && (designersState !== 'ready' || !designerOptions.length)" class="designer-state" role="status">
              <span v-if="designersState === 'loading'">正在加载人员…</span>
              <template v-else-if="designersState === 'error'">
                <span>人员选项加载失败</span>
                <el-button link type="primary" :disabled="saving" @click="loadDesigners">重试</el-button>
              </template>
              <span v-else>暂无可选人员</span>
            </div>
            <div class="editor-grid">
              <el-form-item v-if="current" label="状态" prop="status" for="ad-production-status" data-testid="ad-production-status" @keydown.esc.capture="onSelectEscape($event, statusMenuOpen)">
                <el-select id="ad-production-status" v-model="form.status" class="control" @visible-change="statusMenuOpen = $event" @change="onStatusChange">
                  <el-option v-for="status in statusOptions" :key="status.value" :label="status.label" :value="status.value" />
                </el-select>
              </el-form-item>
              <el-form-item
                v-for="field in visibleDesignerFields"
                :key="field.key"
                :label="field.label"
                :prop="field.key"
                :required="field.key === 'receiver_id' ? !current : isMerchantAd"
                :for="`ad-production-${field.key}`"
                @keydown.esc.capture="onSelectEscape($event, designerMenusOpen[field.key])"
              >
                <el-select
                  :id="`ad-production-${field.key}`"
                  v-model="form[field.key]"
                  class="control"
                  filterable
                  :clearable="!!current"
                  :value-on-clear="null"
                  :disabled="designersState === 'loading' || (!designerOptions.length && form[field.key] === null)"
                  placeholder="搜索人员"
                  @visible-change="designerMenusOpen[field.key] = $event"
                  @change="onDesignerChange(field.key)"
                >
                  <el-option v-for="person in availableDesigners(field.key)" :key="person.id" :label="person.display_name" :value="person.id" :disabled="person.disabled" />
                </el-select>
              </el-form-item>
              <el-form-item v-if="!statusOnly" label="截止时间" for="ad-production-due">
                <el-date-picker
                  id="ad-production-due"
                  v-model="form.due"
                  class="control"
                  type="datetime"
                  format="YYYY-MM-DD HH:mm"
                  :value-on-clear="null"
                  placeholder="选填"
                  popper-class="list-filter-date-popper"
                />
              </el-form-item>
            </div>
            <el-form-item v-if="isMerchantAd && form.status === 'COMPLETED'" label="处理结果" prop="processing_result" for="ad-production-processing-result" required>
              <el-input
                id="ad-production-processing-result"
                v-model="form.processing_result"
                type="textarea"
                :rows="4"
                placeholder="填写实际处理情况"
              />
            </el-form-item>
            <el-form-item v-if="!statusOnly" label="需求内容" prop="content">
              <RichTextEditor
                :key="current?.revision"
                v-model="form.content"
                :ad-production-id="current?.id"
                :disabled="saving"
                label="需求内容"
                @blur="formRef?.validateField('content').catch(() => {})"
              />
              <p v-if="isMerchantAd" class="content-hint">例如，说明要替换的门店、老机器和新机器的二维码（含集合码），或已组装机器送往哪家店。</p>
            </el-form-item>
            <el-form-item v-if="!statusOnly" label="图片">
              <div class="image-section">
                <p class="image-hint">最多 5 张，支持 PNG、JPEG、WebP，单张最多 5 MiB。这里与正文新增的图片合计最多 15 MiB。</p>
                <div v-if="imageCount" class="ad-image-grid">
                  <AdProductionImage
                    v-for="image in keptImages"
                    :key="`stored-${image.file_id}`"
                    :source="{ recordId: current!.id, fileId: image.file_id, name: image.original_name }"
                    remove-label="移除"
                    :disabled="saving"
                    @remove="removeStored(image.file_id)"
                  />
                  <AdProductionImage
                    v-for="image in staged"
                    :key="`local-${image.key}`"
                    :source="{ file: image.file }"
                    remove-label="移除"
                    :disabled="saving"
                    @remove="removeStaged(image.key)"
                  />
                </div>
                <ul v-if="removedImages.length" class="removed-list" aria-label="待移除图片">
                  <li v-for="image in removedImages" :key="image.file_id">
                    <span>保存后移除 {{ image.original_name }}</span>
                    <el-button link type="primary" :disabled="saving || imageCount >= IMAGE_LIMIT" @click="restoreStored(image.file_id)">撤销移除</el-button>
                  </li>
                </ul>
                <input id="ad-production-images-input" ref="fileInput" data-testid="ad-production-images-input" type="file" :accept="AD_PRODUCTION_IMAGE_TYPES.join(',')" multiple hidden :disabled="saving" @change="stageImages" />
                <el-button class="add-images" :disabled="saving || imageCount >= IMAGE_LIMIT" @click="fileInput?.click()"><AppIcon name="plus" :size="16" /> 添加图片</el-button>
                <p v-if="imageError" class="image-error" role="alert">{{ imageError }}</p>
              </div>
            </el-form-item>
          </div>
          <div class="editor-actions">
            <el-button :disabled="saving" @click="cancel">取消</el-button>
            <el-button type="primary" native-type="submit" data-testid="ad-production-save" :disabled="statusOnly && !statusChanged" :loading="saving">{{ current ? '保存' : '发布需求' }}</el-button>
          </div>
        </el-form>
      </SectionCard>
    </section>
  </el-dialog>
  <RevisionConflictDialog
    :visible="conflict.visible"
    :loading="conflict.loading"
    :entity-label="conflict.entityLabel"
    :submitted-revision="conflict.submittedRevision"
    :metadata="conflict.metadata"
    :summary="conflict.summary"
    :read-error="conflict.readError"
    @close="conflict.close"
    @reload="conflict.reload"
  />
</template>

<style scoped>
.editor-card { border: 0; box-shadow: none; }
.status-record-title { margin: 0 0 var(--if-space-3); font-size: 16px; overflow-wrap: anywhere; }
.editor-context { row-gap: var(--if-space-2); margin: 0 0 var(--if-space-4); }
.editor-context dt { color: var(--if-text-secondary); font-size: var(--if-font-caption); }
.editor-context dd { margin: 4px 0 0; overflow-wrap: anywhere; }
.save-error { margin-bottom: var(--if-space-4); }
.designer-state { display: flex; align-items: center; gap: var(--if-space-2); margin: 0 0 var(--if-space-2); color: var(--if-text-3); font-size: var(--if-font-caption); }
.ad-form .control { width: 100%; min-width: 0; }
.ad-form :deep(.el-date-editor.el-input) { --el-date-editor-width: 100%; }
.image-section { display: grid; width: 100%; gap: var(--if-space-2); }
.content-hint { width: 100%; margin: 6px 0 0; color: var(--if-text-2); font-size: var(--if-font-caption); line-height: 1.5; }
.image-hint, .image-error { margin: 0; font-size: var(--if-font-caption); line-height: 1.5; }
.image-hint { color: var(--if-text-3); }
.image-error { color: var(--el-color-danger); overflow-wrap: anywhere; }
.ad-image-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(108px, 1fr)); gap: var(--if-space-3); }
.removed-list { display: grid; gap: 4px; padding: 0; margin: 0; list-style: none; }
.removed-list li { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 12px; color: var(--if-text-2); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.add-images { justify-self: start; }
.add-images :deep(span) { display: inline-flex; gap: 6px; align-items: center; }
@media (max-width: 767px) {
  .add-images, .removed-list :deep(.el-button), .editor-actions .el-button,
  .designer-state .el-button, .ad-form :deep(.el-input__wrapper), .ad-form :deep(.el-select__wrapper) { min-height: 44px; }
  .ad-form :deep(.el-input__inner), .ad-form :deep(.el-select__input), .ad-form :deep(.el-textarea__inner) { font-size: 16px; }
}
</style>
