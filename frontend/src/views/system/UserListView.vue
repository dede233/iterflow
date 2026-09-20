<script setup lang="ts">
import{onMounted,ref}from'vue';import{api}from'@/api/client';const rows=ref<any[]>([]);onMounted(async()=>rows.value=(await api.get('/users')).data.items)
</script>
<template><div class="page"><div class="page-title">用户管理</div><el-table :data="rows"><el-table-column prop="username" label="用户名"/><el-table-column prop="display_name" label="姓名"/><el-table-column prop="email" label="邮箱"/><el-table-column prop="status" label="状态"/></el-table></div></template>
