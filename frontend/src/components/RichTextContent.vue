<script setup lang="ts">
import { computed } from 'vue'
import { sanitizeRichText, type DescriptionFormat } from '@/utils/richText'
const props = withDefaults(defineProps<{ content?: string | null; format?: DescriptionFormat }>(), { content: '', format: 'PLAIN' })
const html = computed(() => props.format === 'HTML' ? sanitizeRichText(props.content || '') : '')
</script>
<template>
  <div v-if="format === 'HTML'" class="rich-text-content" v-html="html" />
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
