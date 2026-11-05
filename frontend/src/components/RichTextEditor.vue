<script setup lang="ts">
import { onBeforeUnmount, provide, ref, useId, watch } from 'vue'
import { EditorContent, Node, VueNodeViewRenderer, useEditor } from '@tiptap/vue-3'
import EditorImageNode from './EditorImageNode.vue'
import { rememberImage, forgetImage, pendingImage } from '@/utils/requirementImages'
import StarterKit from '@tiptap/starter-kit'
import { richTextPlainText, safeRichTextLink, sanitizeRichText } from '@/utils/richText'

const props = withDefaults(defineProps<{ modelValue: string; requirementId?: number; disabled?: boolean; label?: string }>(), { disabled: false, label: '需求描述' })
const emit = defineEmits<{ 'update:modelValue': [value: string]; blur: [] }>()
const linkOpen = ref(false)
const linkUrl = ref('')
const linkError = ref('')
const linkId = useId()
let linkSelection = { from: 1, to: 1 }
const picker = ref<HTMLInputElement>()
const imageError = ref('')
const owned = new Set<string>()
provide('editorRequirementId', () => props.requirementId)
onBeforeUnmount(() => owned.forEach(forgetImage))
const picture = Node.create({
  name: 'requirementImage', group: 'block', atom: true,
  addAttributes: () => ({ fileId: { default: null, parseHTML: el => el.getAttribute('data-file-id'), renderHTML: attrs => ({ 'data-file-id': attrs.fileId }) } }),
  parseHTML: () => [{ tag: 'img[data-file-id]' }],
  renderHTML: ({ HTMLAttributes }) => ['img', HTMLAttributes],
  addNodeView: () => VueNodeViewRenderer(EditorImageNode),
})
function insertImages(files: File[]) {
  const instance = editor.value
  if (!instance || props.disabled) return
  imageError.value = ''
  if (files.some(f => !['image/png', 'image/jpeg', 'image/webp'].includes(f.type) || f.size > 4 * 1024 * 1024)) {
    imageError.value = '请选择 4 MiB 以内的 PNG、JPEG 或 WebP 图片'
    return
  }
  let count = 0, bytes = files.reduce((n, f) => n + f.size, 0)
  instance.state.doc.descendants(node => {
    if (node.type.name === 'requirementImage') { count++; bytes += pendingImage(node.attrs.fileId)?.size || 0 }
  })
  if (count + files.length > 12 || bytes > 8 * 1024 * 1024) {
    imageError.value = '每条需求最多 12 张图片，本次新增图片合计限 8 MiB'
    return
  }
  const nodes = files.map(file => {
    const fileId = rememberImage(file)
    owned.add(fileId)
    return { type: 'requirementImage', attrs: { fileId } }
  })
  const selection = instance.state.selection
  const chain = instance.chain().focus()
  if (selection.$from.nodeAfter?.type.name === 'requirementImage' && !selection.empty)
    chain.insertContentAt(selection.to, nodes).run()
  else chain.insertContent(nodes).run()
}
function choosePictures(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files?.length) insertImages(Array.from(input.files))
  input.value = ''
}
const editor = useEditor({
  content: sanitizeRichText(props.modelValue),
  editable: !props.disabled,
  extensions: [picture, StarterKit.configure({
    heading: { levels: [2, 3] },
    horizontalRule: false,
    underline: false,
    link: { openOnClick: false, autolink: false, linkOnPaste: false, isAllowedUri: safeRichTextLink },
  })],
  editorProps: {
    attributes: { role: 'textbox', 'aria-label': props.label, 'aria-multiline': 'true' },
    handleDOMEvents: { paste(_view, event) {
      const files = Array.from(event.clipboardData?.files || [])
      if (!files.length) return false
      event.preventDefault()
      insertImages(files)
      return true
    } },
    transformPastedHTML: sanitizeRichText,
  },
  onUpdate: ({ editor: current }) => {
    linkOpen.value = false
    if (!props.disabled) emit('update:modelValue', sanitizeRichText(current.getHTML()))
  },
  onBlur: () => emit('blur'),
})
watch(() => props.modelValue, value => {
  const clean = sanitizeRichText(value)
  if (editor.value && editor.value.getHTML() !== clean) {
    linkOpen.value = false
    editor.value.commands.setContent(clean, { emitUpdate: false })
  }
})
watch(() => props.disabled, disabled => {
  editor.value?.setEditable(!disabled, false)
  if (disabled) linkOpen.value = false
})
watch(() => props.label, label => editor.value?.setOptions({ editorProps: { attributes: { role: 'textbox', 'aria-label': label, 'aria-multiline': 'true' } } }))
type Command = 'paragraph' | 'heading' | 'bold' | 'italic' | 'bulletList' | 'orderedList' | 'undo' | 'redo'
function command(name: Command) {
  if (!editor.value || props.disabled) return
  const chain = editor.value.chain().focus()
  if (name === 'paragraph') chain.setParagraph().run()
  else if (name === 'heading') chain.toggleHeading({ level: 2 }).run()
  else if (name === 'bold') chain.toggleBold().run()
  else if (name === 'italic') chain.toggleItalic().run()
  else if (name === 'bulletList') chain.toggleBulletList().run()
  else if (name === 'orderedList') chain.toggleOrderedList().run()
  else if (name === 'undo') chain.undo().run()
  else chain.redo().run()
}
function openLink() {
  if (!editor.value || props.disabled) return
  linkSelection = { from: editor.value.state.selection.from, to: editor.value.state.selection.to }
  linkUrl.value = editor.value.getAttributes('link').href || ''
  linkError.value = ''
  linkOpen.value = !linkOpen.value
}
function applyLink() {
  if (!editor.value || props.disabled) return
  const href = linkUrl.value.trim()
  if (!safeRichTextLink(href)) { linkError.value = '请输入完整的 http://、https:// 或 mailto: 链接'; return }
  const chain = editor.value.chain().focus().setTextSelection(linkSelection)
  if (linkSelection.from === linkSelection.to && !editor.value.isActive('link')) {
    chain.insertContent({ type: 'text', text: href, marks: [{ type: 'link', attrs: { href } }] }).run()
  } else chain.extendMarkRange('link').setLink({ href }).run()
  linkOpen.value = false
}
function removeLink() {
  if (!editor.value || props.disabled) return
  editor.value.chain().focus().setTextSelection(linkSelection).extendMarkRange('link').unsetLink().run()
  linkOpen.value = false
}
</script>
<template>
  <div class="rich-text-editor" :class="{ disabled }">
    <div class="editor-toolbar" role="group" :aria-label="`${label}格式`">
      <button type="button" :disabled="disabled" :aria-pressed="editor?.isActive('paragraph') || false" @mousedown.prevent @click="command('paragraph')">正文</button>
      <button type="button" :disabled="disabled" :aria-pressed="editor?.isActive('heading') || false" @mousedown.prevent @click="command('heading')">标题</button>
      <button type="button" aria-label="加粗" :disabled="disabled" :aria-pressed="editor?.isActive('bold') || false" @mousedown.prevent @click="command('bold')"><strong>加粗</strong></button>
      <button type="button" aria-label="斜体" :disabled="disabled" :aria-pressed="editor?.isActive('italic') || false" @mousedown.prevent @click="command('italic')"><em>斜体</em></button>
      <button type="button" :disabled="disabled" :aria-pressed="editor?.isActive('bulletList') || false" @mousedown.prevent @click="command('bulletList')">无序列表</button>
      <button type="button" :disabled="disabled" :aria-pressed="editor?.isActive('orderedList') || false" @mousedown.prevent @click="command('orderedList')">有序列表</button>
      <button type="button" :disabled="disabled" @mousedown.prevent @click="picker?.click()">插入图片</button>
      <input ref="picker" type="file" hidden multiple accept="image/png,image/jpeg,image/webp" @change="choosePictures">
      <button type="button" :disabled="disabled" :aria-expanded="linkOpen" @mousedown.prevent @click="openLink">链接</button>
      <button type="button" :disabled="disabled || !editor?.can().undo()" @mousedown.prevent @click="command('undo')">撤销</button>
      <button type="button" :disabled="disabled || !editor?.can().redo()" @mousedown.prevent @click="command('redo')">重做</button>
    </div>
    <div v-if="linkOpen" class="link-editor">
      <label :for="linkId">链接地址</label>
      <input :id="linkId" v-model="linkUrl" type="url" placeholder="https://example.com" :aria-invalid="!!linkError" @keydown.enter.prevent="applyLink" @keydown.escape.prevent="linkOpen = false" />
      <button type="button" @click="applyLink">应用链接</button>
      <button type="button" @click="removeLink">移除链接</button>
      <button type="button" @click="linkOpen = false">取消</button>
      <p v-if="linkError" role="alert">{{ linkError }}</p>
    </div>
    <p v-if="imageError" role="alert">{{ imageError }}</p>
    <EditorContent :editor="editor" />
    <p class="editor-hint">支持标题、列表、加粗和链接，可直接粘贴截图<span v-if="richTextPlainText(modelValue).length > 20000"> · 内容较长，建议精简后保存</span></p>
  </div>
</template>
<style scoped>
.rich-text-editor { width: 100%; min-width: 0; border: 1px solid var(--el-border-color); border-radius: var(--el-border-radius-base); overflow: hidden; }
.rich-text-editor:focus-within { border-color: var(--el-color-primary); }
.editor-toolbar { display: flex; flex-wrap: wrap; gap: 4px; padding: 6px; border-bottom: 1px solid var(--el-border-color); background: var(--if-bg-muted); }
button { min-height: 32px; border: 1px solid transparent; border-radius: 4px; padding: 4px 8px; background: transparent; color: var(--el-text-color-primary); cursor: pointer; font: inherit; font-size: 12px; }
button:hover:not(:disabled), button[aria-pressed="true"] { color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
button:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: -2px; }
button:disabled { opacity: .5; cursor: not-allowed; }
.rich-text-editor :deep(.tiptap) { min-height: 160px; max-height: 440px; overflow-y: auto; padding: 10px 12px; outline: none; line-height: 1.7; overflow-wrap: anywhere; }
.rich-text-editor :deep(.tiptap p) { margin: .3em 0; }
.rich-text-editor :deep(.tiptap h2) { font-size: 1.35em; }
.rich-text-editor :deep(.tiptap h3) { font-size: 1.15em; }
.rich-text-editor :deep(.tiptap ul), .rich-text-editor :deep(.tiptap ol) { padding-left: 1.7em; }
.rich-text-editor :deep(.tiptap a) { color: var(--el-color-primary); text-decoration: underline; }
.rich-text-editor :deep(.tiptap pre) { white-space: pre-wrap; }
.editor-hint { margin: 0; padding: 6px 12px; color: var(--el-text-color-secondary); font-size: 12px; }
.link-editor { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; padding: 8px; background: var(--if-bg-muted); font-size: 12px; }
.link-editor input { flex: 1; min-width: 140px; max-width: 100%; min-height: 32px; border: 1px solid var(--el-border-color); border-radius: 4px; padding: 4px 8px; }
.link-editor p { flex-basis: 100%; margin: 0; color: var(--el-color-danger); }
.disabled { background: var(--el-fill-color-light); }
@media (max-width: 767px) { button, .link-editor input { min-height: 44px; } }
</style>
