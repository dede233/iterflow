<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ status: string; label?: string; type?: string }>()

const DEFAULT_TYPES: Record<string, string> = {
  ONLINE: 'success',
  RELEASED: 'success',
  DONE: 'success',
  DEVELOPING: 'primary',
  TESTING: 'warning',
  READY: 'warning',
  CANCELED: 'info',
  CLOSED: 'info',
}

const tagType = computed(() => props.type ?? DEFAULT_TYPES[props.status] ?? '')
const text = computed(() => props.label ?? props.status)
</script>

<template>
  <el-tag :type="tagType" effect="light">{{ text }}</el-tag>
</template>
