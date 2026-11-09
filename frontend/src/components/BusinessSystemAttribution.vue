<script setup lang="ts">
defineProps<{ systemId?: number | null; systemName?: string | null }>()
</script>

<template>
  <p class="system-attribution"><span>业务系统</span><strong>{{ systemName || (systemId != null ? `系统 #${systemId}` : '未指定') }}</strong></p>
</template>

<style scoped>
.system-attribution { display: flex; align-items: baseline; flex-wrap: wrap; gap: 6px 12px; margin: 0 0 16px; font-size: 13px; overflow-wrap: anywhere; }
.system-attribution span { color: var(--if-text-secondary); }
.system-attribution strong { font-weight: 500; color: var(--if-text-primary); }
</style>
