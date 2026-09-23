<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import MobileBottomNav from '@/components/MobileBottomNav.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
interface NavigationItem {
  to: string
  label: string
  permission?: string | string[]
  requiresAllScope?: boolean
}

const menuItems = computed<NavigationItem[]>(() => [
  { to: '/', label: '首页', permission: 'dashboard.view' },
  { to: '/feedbacks', label: '反馈中心', permission: 'rd.feedback.view' },
  { to: '/requirements', label: '需求管理', permission: 'rd.requirement.view' },
  { to: '/versions', label: '版本管理', permission: 'rd.version.view' },
  { to: '/releases', label: '发布记录', permission: 'rd.release.view' },
  { to: '/notifications', label: '通知中心' },
])
const systemItems = computed<NavigationItem[]>(() => [
  { to: '/admin/audits', label: '审计中心', permission: 'sys.audit.view' },
  { to: '/system/users', label: '用户管理', permission: 'sys.user.view' },
  { to: '/admin/roles', label: '角色管理', permission: ['sys.role.view', 'sys.role.manage'], requiresAllScope: true },
])

function can(permission?: string | string[], requiresAllScope = false): boolean {
  return (!permission || auth.hasPermission(permission)) && (!requiresAllScope || auth.user?.data_scope === 'ALL')
}

async function logout(): Promise<void> {
  await auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="shell">
    <aside class="side desktop-only">
      <div class="brand">迭程 IterFlow</div>
      <router-link v-for="item in menuItems.filter((item) => can(item.permission, item.requiresAllScope))" :key="item.to" :to="item.to">
        {{ item.label }}
      </router-link>
      <template v-if="systemItems.some((item) => can(item.permission, item.requiresAllScope))">
        <div class="group">系统设置</div>
        <router-link v-for="item in systemItems.filter((item) => can(item.permission, item.requiresAllScope))" :key="item.to" :to="item.to">
          {{ item.label }}
        </router-link>
      </template>
      <div class="account">
        <span>{{ auth.user?.display_name }}</span>
        <el-button text type="primary" @click="logout">退出登录</el-button>
      </div>
    </aside>
    <main class="content"><router-view /></main>
    <MobileBottomNav />
  </div>
</template>

<style scoped>
.shell { min-height: 100vh; }
.side { position: fixed; inset: 0 auto 0 0; display: flex; width: 220px; flex-direction: column; gap: 8px; padding: 18px; color: #dbeafe; background: #16243a; }
.brand { margin-bottom: 14px; color: #fff; font-size: 18px; font-weight: 800; }
.side a { padding: 10px; border-radius: 7px; }
.side .router-link-active { color: #fff; background: #1677ff; }
.group { margin-top: 12px; color: #94a3b8; font-size: 12px; }
.account { display: grid; gap: 4px; margin-top: auto; padding-top: 16px; color: #cbd5e1; font-size: 13px; }
.account .el-button { justify-content: flex-start; width: fit-content; padding-left: 0; }
.content { min-height: 100vh; margin-left: 220px; }
@media (max-width: 767px) { .content { margin-left: 0; } }
</style>
