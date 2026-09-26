<script setup lang="ts">
import AppIcon from './AppIcon.vue'
defineProps<{ title: string; description?: string; retryLabel?: string }>()
defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="error-state" role="alert">
    <span class="error-state__icon"><AppIcon name="alert" :size="24" /></span>
    <h2>{{ title }}</h2>
    <p v-if="description">{{ description }}</p>
    <el-button v-if="retryLabel" type="primary" @click="$emit('retry')">{{ retryLabel }}</el-button>
    <slot />
  </div>
</template>

<style scoped>
.error-state { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 48px 16px; text-align: center; background: var(--if-bg-surface); border: 1px solid var(--if-border); border-radius: var(--if-radius); }
.error-state__icon { display: grid; place-items: center; width: 52px; height: 52px; border-radius: 50%; background: var(--if-danger-bg); color: var(--if-danger-fg); }
h2 { margin: 4px 0 0; font-size: 16px; }
p { margin: 0; color: var(--if-text-2); font-size: 13px; }
</style>
