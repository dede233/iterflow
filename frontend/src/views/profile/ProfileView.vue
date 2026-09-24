<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function logout(): Promise<void> {
  await auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="page profile-page">
    <h1 class="page-title">个人中心</h1>
    <el-card class="profile-card" shadow="never">
      <template #header><strong>账号信息</strong></template>
      <dl class="details">
        <div><dt>显示名称</dt><dd>{{ auth.user?.display_name }}</dd></div>
        <div><dt>用户名</dt><dd>{{ auth.user?.username }}</dd></div>
        <div><dt>邮箱</dt><dd>{{ auth.user?.email || '未设置' }}</dd></div>
        <div><dt>账号状态</dt><dd>{{ auth.user?.status }}</dd></div>
        <div><dt>数据范围</dt><dd>{{ auth.user?.data_scope }}</dd></div>
      </dl>
      <div class="actions">
        <el-button type="primary" @click="router.push('/change-password?from=profile')">修改密码</el-button>
        <el-button @click="logout">退出登录</el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.profile-page { max-width: 760px; }
.profile-card { width: 100%; }
.details { margin: 0; }
.details > div { display: grid; grid-template-columns: 112px minmax(0, 1fr); gap: 12px; padding: 12px 0; border-bottom: 1px solid #eef0f3; }
.details dt { color: #64748b; }
.details dd { min-width: 0; margin: 0; overflow-wrap: anywhere; }
.actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 24px; }
.actions :deep(.el-button) { margin-left: 0; }
@media (max-width: 767px) {
  .details > div { grid-template-columns: 1fr; gap: 4px; }
  .actions { flex-direction: column; }
  .actions :deep(.el-button) { width: 100%; min-height: 44px; }
}
</style>
