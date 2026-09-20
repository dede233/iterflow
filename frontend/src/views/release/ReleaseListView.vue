<script setup lang="ts">
import{onMounted,ref}from'vue';import{api}from'@/api/client';const rows=ref<any[]>([]);onMounted(async()=>rows.value=(await api.get('/releases')).data.items)
</script>
<template><div class="page"><div class="page-title">发布记录</div><el-table :data="rows"><el-table-column prop="version_id" label="版本ID"/><el-table-column prop="released_at" label="发布时间"/><el-table-column prop="result" label="结果"/><el-table-column prop="release_notes" label="发布说明" min-width="260"/></el-table></div></template>
