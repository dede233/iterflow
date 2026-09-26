<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import MobileBottomNav from '@/components/MobileBottomNav.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
interface NavigationItem {
  to: string
  label: string
  icon: string
  permission?: string | string[]
  requiresAllScope?: boolean
}
interface NavigationGroup {
  label: string
  items: NavigationItem[]
}

const groups = computed<NavigationGroup[]>(() => [
  {
    label: '工作台',
    items: [
      { to: '/', label: '首页', icon: 'home', permission: 'dashboard.view' },
      { to: '/notifications', label: '通知中心', icon: 'bell' },
    ],
  },
  {
    label: '研发协作',
    items: [
      { to: '/feedbacks', label: '反馈中心', icon: 'feedback', permission: 'rd.feedback.view' },
      { to: '/requirements', label: '需求管理', icon: 'requirement', permission: 'rd.requirement.view' },
      { to: '/versions', label: '版本管理', icon: 'version', permission: 'rd.version.view' },
    ],
  },
  {
    label: '发布',
    items: [{ to: '/releases', label: '发布记录', icon: 'release', permission: 'rd.release.view' }],
  },
  {
    label: '系统设置',
    items: [
      { to: '/admin/audits', label: '审计中心', icon: 'audit', permission: 'sys.audit.view' },
      { to: '/admin/systems', label: '系统与模块', icon: 'system', permission: 'sys.system.manage', requiresAllScope: true },
      { to: '/system/users', label: '用户管理', icon: 'users', permission: 'sys.user.view' },
      { to: '/admin/roles', label: '角色管理', icon: 'shield', permission: ['sys.role.view', 'sys.role.manage'], requiresAllScope: true },
    ],
  },
])

function can(permission?: string | string[], requiresAllScope = false): boolean {
  return (!permission || auth.hasPermission(permission)) && (!requiresAllScope || auth.user?.data_scope === 'ALL')
}

const visibleGroups = computed(() =>
  groups.value
    .map((group) => ({ ...group, items: group.items.filter((item) => can(item.permission, item.requiresAllScope)) }))
    .filter((group) => group.items.length),
)
const initial = computed(() => (auth.user?.display_name || auth.user?.username || '?').slice(0, 1).toUpperCase())

async function logout(): Promise<void> {
  await auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="shell">
    <aside class="side desktop-only" aria-label="侧边导航">
      <div class="brand">
        <span class="brand-mark">迭</span>
        <span class="brand-text"><strong>迭程</strong> IterFlow</span>
      </div>
      <nav class="side-nav">
        <div v-for="group in visibleGroups" :key="group.label" class="nav-group">
          <div class="group">{{ group.label }}</div>
          <router-link v-for="item in group.items" :key="item.to" :to="item.to" class="nav-link" :class="{ home: item.to === '/' }">
            <AppIcon :name="item.icon" />
            <span>{{ item.label }}</span>
          </router-link>
        </div>
      </nav>
      <div class="account">
        <router-link to="/profile" class="account-link">
          <span class="avatar">{{ initial }}</span>
          <span class="account-text">
            <span class="account-name">{{ auth.user?.display_name }}</span>
            <span class="account-sub">个人中心</span>
          </span>
        </router-link>
        <el-button class="logout" text @click="logout">
          <AppIcon name="logout" :size="16" /><span>退出登录</span>
        </el-button>
      </div>
    </aside>
    <header class="mobile-header mobile-only">
      <span class="brand-mark">迭</span>
      <span class="brand-text"><strong>迭程</strong> IterFlow</span>
    </header>
    <main class="content"><router-view /></main>
    <MobileBottomNav />
  </div>
</template>

<style scoped>
.shell { min-height: 100vh; }
.side { position: fixed; inset: 0 auto 0 0; z-index: 30; display: flex; width: var(--if-sidebar-width); flex-direction: column; padding: 18px 12px 12px; color: #cbd5e1; background: var(--if-bg-sidebar); }
.brand { display: flex; align-items: center; gap: 10px; padding: 0 8px 18px; color: #fff; }
.brand-mark { display: grid; place-items: center; width: 30px; height: 30px; border-radius: 8px; background: linear-gradient(135deg, #5b8cff, #3b6cf6); color: #fff; font-size: 15px; font-weight: 800; }
.brand-text { font-size: 15px; letter-spacing: .01em; }
.side-nav { flex: 1; overflow-y: auto; }
.nav-group + .nav-group { margin-top: 14px; }
.group { padding: 0 10px 6px; color: #64748b; font-size: 11px; font-weight: 600; letter-spacing: .06em; }
.nav-link { display: flex; align-items: center; gap: 10px; height: 38px; padding: 0 10px; border-radius: 8px; color: #cbd5e1; font-size: 14px; transition: background .15s, color .15s; }
.nav-link:hover { background: rgba(255, 255, 255, .06); color: #fff; }
.nav-link.router-link-exact-active,
.nav-link.router-link-active:not(.home) { background: rgba(91, 140, 255, .18); color: #fff; box-shadow: inset 3px 0 0 #5b8cff; }
.nav-link:focus-visible { outline: 2px solid #91b1ff; outline-offset: -2px; }
.account { display: grid; gap: 4px; margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(255, 255, 255, .08); }
.account-link { display: flex; align-items: center; gap: 10px; padding: 8px; border-radius: 8px; }
.account-link:hover, .account-link.router-link-active { background: rgba(255, 255, 255, .06); }
.avatar { display: grid; place-items: center; flex-shrink: 0; width: 32px; height: 32px; border-radius: 50%; background: #334155; color: #fff; font-weight: 700; }
.account-text { display: grid; min-width: 0; }
.account-name { overflow: hidden; color: #fff; font-size: 13px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.account-sub { color: #94a3b8; font-size: 12px; }
.logout { justify-content: flex-start; gap: 8px; height: 34px; margin: 0; padding: 0 10px; color: #94a3b8; }
.logout:hover { color: #fff; background: rgba(255, 255, 255, .06) !important; }
.logout :deep(span) { display: inline-flex; align-items: center; gap: 8px; }
.content { min-width: 0; min-height: 100vh; margin-left: var(--if-sidebar-width); }
.mobile-header { position: sticky; top: 0; z-index: 20; align-items: center; gap: 8px; height: 50px; padding: 0 14px; background: rgba(255, 255, 255, .92); border-bottom: 1px solid var(--if-border); backdrop-filter: blur(8px); }
.mobile-header .brand-mark { width: 26px; height: 26px; font-size: 13px; }
@media (max-width: 767px) {
  .content { min-height: auto; margin-left: 0; }
  .mobile-header { display: flex; }
}
</style>
