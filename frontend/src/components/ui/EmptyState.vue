<script setup lang="ts">
import AppIcon from './AppIcon.vue'
defineProps<{ description: string; icon?: string; compact?: boolean }>()
</script>

<template>
  <div class="empty-state" :class="{ compact }" role="status">
    <span class="empty-state__icon"><AppIcon :name="icon ?? 'inbox'" :size="compact ? 20 : 26" /></span>
    <p class="empty-state__text">{{ description }}</p>
    <div v-if="$slots.default" class="empty-state__action"><slot /></div>
  </div>
</template>

<style scoped>
.empty-state { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 40px 16px; color: var(--if-text-3); text-align: center; }
.empty-state.compact { padding: 20px 12px; gap: 6px; }
.empty-state__icon { display: grid; place-items: center; width: 52px; height: 52px; border-radius: 50%; background: var(--if-bg-subtle); color: var(--if-text-3); }
.compact .empty-state__icon { width: 38px; height: 38px; }
.empty-state__text { margin: 0; font-size: 13px; color: var(--if-text-2); }
</style>
