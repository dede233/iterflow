<script setup lang="ts">
import{onMounted,ref}from'vue';import{api}from'@/api/client';const rows=ref<any[]>([]);onMounted(async()=>rows.value=(await api.get('/roles')).data)
</script>
<template><div class="page"><div class="page-title">角色与权限</div><el-alert title="该页面建议在 PC 端使用" type="info" show-icon/><el-table :data="rows" style="margin-top:12px"><el-table-column prop="code" label="编码"/><el-table-column prop="name" label="角色"/><el-table-column prop="data_scope" label="数据范围"/><el-table-column prop="enabled" label="启用"/></el-table></div></template>
