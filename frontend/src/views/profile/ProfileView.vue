<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'

const auth = useAuthStore()
const router = useRouter()
const initial = computed(() => (auth.user?.display_name || auth.user?.username || '?').slice(0, 1).toUpperCase())

async function logout(): Promise<void> {
  await auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="page profile-page">
    <PageHeader title="个人中心" description="查看账号资料与安全设置。" eyebrow="我的" />
    <SectionCard title="账号信息" class="profile-card">
      <div class="identity">
        <span class="identity-avatar">{{ initial }}</span>
        <div class="identity-text"><strong>{{ auth.user?.display_name }}</strong><span>@{{ auth.user?.username }}</span></div>
        <StatusTag :status="auth.user?.status ?? 'ACTIVE'" :label="auth.user?.status === 'ACTIVE' ? '启用' : '停用'" />
      </div>
      <dl class="details">
        <div><dt>显示名称</dt><dd>{{ auth.user?.display_name }}</dd></div>
        <div><dt>用户名</dt><dd>{{ auth.user?.username }}</dd></div>
        <div><dt>邮箱</dt><dd>{{ auth.user?.email || '未设置' }}</dd></div>
        <div><dt>账号状态</dt><dd>{{ auth.user?.status === 'ACTIVE' ? '启用' : '停用' }}</dd></div>
        <div><dt>数据范围</dt><dd>{{ auth.user?.data_scope === 'ALL' ? '全部数据' : auth.user?.data_scope === 'TEAM' ? '团队数据' : '我的数据' }}</dd></div>
      </dl>
      <div class="actions">
        <el-button type="primary" @click="router.push('/change-password?from=profile')">修改密码</el-button>
        <el-button @click="logout">退出登录</el-button>
      </div>
    </SectionCard>
  </div>
</template>

<style scoped>
.profile-page { max-width: 860px; }
.profile-card { width: 100%; }
.identity { display: flex; align-items: center; gap: 14px; min-width: 0; padding-bottom: 18px; margin-bottom: 4px; border-bottom: 1px solid var(--if-border); }
.identity-avatar { display: grid; place-items: center; flex: 0 0 48px; height: 48px; border-radius: 14px; background: var(--if-brand-50); color: var(--if-brand-700); font-size: 20px; font-weight: 750; }
.identity-text { display: grid; gap: 3px; min-width: 0; flex: 1; }
.identity-text strong { font-size: 17px; overflow-wrap: anywhere; }
.identity-text span { color: var(--if-text-3); font-size: 12px; overflow-wrap: anywhere; }
.details { margin: 0; }
.details > div { display: grid; grid-template-columns: 112px minmax(0, 1fr); gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--if-border); }
.details dt { color: var(--if-text-3); }
.details dd { min-width: 0; margin: 0; overflow-wrap: anywhere; }
.actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 24px; }
.actions :deep(.el-button) { margin-left: 0; }
@media (max-width: 767px) {
  .details > div { grid-template-columns: 1fr; gap: 4px; }
  .actions { flex-direction: column; }
  .actions :deep(.el-button) { width: 100%; min-height: 44px; }
}
</style>
