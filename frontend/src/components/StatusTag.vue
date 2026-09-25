<script setup lang="ts">
import { computed } from 'vue'

// Unified status badge. `type` accepts the Element-style names returned by the
// *StatusTagType helpers, or a semantic tone; both map onto the token palette.
const props = defineProps<{ status: string; label?: string; type?: string; size?: 'sm' | 'md' }>()

const DEFAULT_TONES: Record<string, string> = {
  NEW: 'warning', ACCEPTED: 'info', REQUIREMENT_LINKED: 'info',
  DRAFT: 'neutral', CONFIRMED: 'info', PLANNED: 'info', PLANNING: 'neutral',
  DEVELOPING: 'progress', TESTING: 'warning', READY: 'warning', PAUSED: 'warning',
  ONLINE: 'success', RELEASED: 'success', DONE: 'success', SUCCESS: 'success', ACTIVE: 'success', ENABLED: 'success',
  CANCELED: 'neutral', CLOSED: 'neutral', DISABLED: 'neutral', DUPLICATE: 'neutral', CANNOT_REPRODUCE: 'neutral',
  FAILED: 'danger', UNREAD: 'info', READ: 'neutral',
}
const TYPE_TO_TONE: Record<string, string> = {
  primary: 'info', success: 'success', warning: 'warning', danger: 'danger', info: 'neutral',
}

const tone = computed(() => {
  const raw = DEFAULT_TONES[props.status] || props.type || 'neutral'
  return TYPE_TO_TONE[raw] ?? raw
})
const text = computed(() => props.label ?? props.status)
</script>

<template>
  <span class="status-tag" :class="[`tone-${tone}`, `size-${size ?? 'md'}`]" :data-status="status">
    <span class="status-tag__dot" aria-hidden="true" />{{ text }}
  </span>
</template>

<style scoped>
.status-tag { display: inline-flex; align-items: center; gap: 6px; height: 24px; padding: 0 9px; border-radius: 999px; font-size: 12px; font-weight: 600; line-height: 1; white-space: nowrap; }
.status-tag.size-sm { height: 20px; padding: 0 7px; font-size: 11px; }
.status-tag__dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.tone-neutral { background: var(--if-neutral-bg); color: var(--if-neutral-fg); }
.tone-info { background: var(--if-info-bg); color: var(--if-info-fg); }
.tone-progress { background: var(--if-progress-bg); color: var(--if-progress-fg); }
.tone-warning { background: var(--if-warning-bg); color: var(--if-warning-fg); }
.tone-success { background: var(--if-success-bg); color: var(--if-success-fg); }
.tone-danger { background: var(--if-danger-bg); color: var(--if-danger-fg); }
</style>
