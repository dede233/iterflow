<script setup lang="ts">
import { computed } from 'vue'

// Unified status badge V2.
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
    <span class="status-tag__dot" aria-hidden="true" />
    <span class="status-tag__text">{{ text }}</span>
  </span>
</template>

<style scoped>
.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 22px;
  padding: 0 8px;
  border-radius: var(--if-radius-full);
  font-size: 12px;
  font-weight: 500;
  line-height: 1;
  white-space: nowrap;
  border: 1px solid transparent;
  letter-spacing: 0.01em;
}
.status-tag.size-sm {
  height: 18px;
  padding: 0 6px;
  font-size: 11px;
  gap: 4px;
}
.status-tag__dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background-color: currentColor;
  flex-shrink: 0;
}
.status-tag.size-sm .status-tag__dot {
  width: 4px;
  height: 4px;
}
.status-tag__text {
  line-height: 1;
}

.tone-neutral {
  background-color: var(--if-neutral-bg);
  color: var(--if-neutral-fg);
  border-color: var(--if-neutral-border);
}
.tone-info {
  background-color: var(--if-info-bg);
  color: var(--if-info-fg);
  border-color: var(--if-info-border);
}
.tone-progress {
  background-color: var(--if-progress-bg);
  color: var(--if-progress-fg);
  border-color: var(--if-progress-border);
}
.tone-warning {
  background-color: var(--if-warning-bg);
  color: var(--if-warning-fg);
  border-color: var(--if-warning-border);
}
.tone-success {
  background-color: var(--if-success-bg);
  color: var(--if-success-fg);
  border-color: var(--if-success-border);
}
.tone-danger {
  background-color: var(--if-danger-bg);
  color: var(--if-danger-fg);
  border-color: var(--if-danger-border);
}
</style>
