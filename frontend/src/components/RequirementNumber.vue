<script setup lang="ts">
defineProps<{ number: string }>()
</script>

<template>
  <div class="requirement-number">
    <span>需求编号</span>
    <strong>{{ number }}</strong>
  </div>
</template>

<style scoped>
.requirement-number { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 8px; color: var(--if-text-2); font: 14px/1.5 var(--if-font-sans, sans-serif); }
strong { color: var(--if-text-1); font-family: var(--if-font-mono); user-select: all; }
</style>
