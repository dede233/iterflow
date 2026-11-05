<script setup lang="ts">
import { h, type VNodeChild } from 'vue'
import { sanitizeRichText, type DescriptionFormat } from '@/utils/richText'
import RequirementImage from './RequirementImage.vue'
const props = withDefaults(defineProps<{ requirementId?: number; content?: string | null; format?: DescriptionFormat }>(), { content: '', format: 'PLAIN' })
function renderNode(node: ChildNode): VNodeChild {
  if (!(node instanceof HTMLElement)) return node.textContent || ''
  if (node.tagName === 'IMG') return h(RequirementImage, { fileId: node.getAttribute('data-file-id')!, requirementId: props.requirementId })
  return h(node.tagName.toLowerCase(), Object.fromEntries(Array.from(node.attributes, a => [a.name, a.value])),
    Array.from(node.childNodes, renderNode))
}
function HtmlContent() {
  const fragment = document.createElement('template')
  fragment.innerHTML = sanitizeRichText(props.content || '')
  return h('div', { class: 'rich-text-content' }, Array.from(fragment.content.childNodes, renderNode))
}
</script>
<template>
  <HtmlContent v-if="format === 'HTML'" />
  <div v-else class="rich-text-content plain">{{ content || '—' }}</div>
</template>
<style scoped>
.rich-text-content { min-width: 0; max-width: 100%; overflow-wrap: anywhere; line-height: 1.7; }
.plain { white-space: pre-wrap; }
.rich-text-content :deep(p) { margin: .4em 0; }
.rich-text-content :deep(h2) { font-size: 1.35em; margin: .7em 0 .4em; }
.rich-text-content :deep(h3) { font-size: 1.15em; margin: .7em 0 .4em; }
.rich-text-content :deep(ul), .rich-text-content :deep(ol) { padding-left: 1.7em; }
.rich-text-content :deep(blockquote) { border-left: 3px solid var(--if-border); margin: .5em 0; padding-left: 1em; }
.rich-text-content :deep(pre) { white-space: pre-wrap; padding: .6em; background: var(--if-bg-muted); }
.rich-text-content :deep(a) { color: var(--el-color-primary); text-decoration: underline; }
</style>
