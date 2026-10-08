<script setup lang="ts">
import AppIcon from './AppIcon.vue'
defineProps<{ title: string; description?: string; retryLabel?: string }>()
defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="error-state" role="alert">
    <div class="error-state__icon-wrap">
      <AppIcon name="alert" :size="24" />
    </div>
    <h2 class="error-state__title">{{ title }}</h2>
    <p v-if="description" class="error-state__desc">{{ description }}</p>
    <el-button v-if="retryLabel" type="primary" class="error-state__btn" @click="$emit('retry')">{{ retryLabel }}</el-button>
    <slot />
  </div>
</template>

<style scoped>
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 48px 24px;
  text-align: center;
  background-color: var(--if-bg-surface);
  border: 1px solid var(--if-border);
  border-radius: var(--if-radius);
}
.error-state__icon-wrap {
  display: grid;
  place-items: center;
  width: 52px;
  height: 52px;
  border-radius: var(--if-radius-lg);
  background-color: var(--if-danger-bg);
  color: var(--if-danger-fg);
  border: 1px solid var(--if-danger-border);
}
.error-state__title {
  margin: 4px 0 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--if-text-primary);
}
.error-state__desc {
  margin: 0;
  color: var(--if-text-secondary);
  font-size: 13px;
  max-width: 360px;
  line-height: 1.5;
}
.error-state__btn {
  margin-top: 8px;
}
</style>
