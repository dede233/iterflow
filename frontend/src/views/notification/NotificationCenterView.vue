<script setup lang="ts">
import{onMounted,ref}from'vue';import{listNotifications,markNotificationRead}from'@/api/notifications';const rows=ref<any[]>([]);async function load(){rows.value=await listNotifications()}async function read(id:number){await markNotificationRead(id);load()}onMounted(load)
</script>
<template><div class="page"><div class="page-title">通知中心</div><div class="cards"><el-card v-for="r in rows" :key="r.id" @click="read(r.id)" :class="{unread:!r.read_at}"><b>{{r.title}}</b><p>{{r.content}}</p><small>{{r.created_at}}</small></el-card></div></div></template><style scoped>.cards{display:grid;gap:10px}.unread{border-left:4px solid #409eff}</style>
