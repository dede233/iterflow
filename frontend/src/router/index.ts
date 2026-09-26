import { createRouter, createWebHashHistory } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'
import { pinia } from '@/stores/pinia'

declare module 'vue-router' {
  interface RouteMeta {
    permission?: string | string[]
    public?: boolean
    allowPasswordChangeRequired?: boolean
    requiresAllScope?: boolean
  }
}

export const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/auth/LoginView.vue'), meta: { public: true } },
    {
      path: '/change-password',
      name: 'change-password',
      component: () => import('@/views/auth/ChangePasswordView.vue'),
      meta: { allowPasswordChangeRequired: true },
    },
    { path: '/forbidden', name: 'forbidden', component: () => import('@/views/auth/ForbiddenView.vue') },
    {
      path: '/',
      component: AppLayout,
      children: [
        { path: '', name: 'dashboard', component: () => import('@/views/dashboard/DashboardView.vue'), meta: { permission: 'dashboard.view' } },
        { path: 'feedbacks', name: 'feedback-list', component: () => import('@/views/feedback/FeedbackListView.vue'), meta: { permission: 'rd.feedback.view' } },
        { path: 'feedbacks/new', name: 'feedback-create', component: () => import('@/views/feedback/FeedbackCreateView.vue'), meta: { permission: 'rd.feedback.create' } },
        { path: 'feedbacks/:id', name: 'feedback-detail', component: () => import('@/views/feedback/FeedbackDetailView.vue'), meta: { permission: 'rd.feedback.view' } },
        { path: 'requirements', name: 'requirement-list', component: () => import('@/views/requirement/RequirementListView.vue'), meta: { permission: 'rd.requirement.view' } },
        { path: 'requirements/new', name: 'requirement-create', component: () => import('@/views/requirement/RequirementCreateView.vue'), meta: { permission: 'rd.requirement.create' } },
        { path: 'requirements/:id', name: 'requirement-detail', component: () => import('@/views/requirement/RequirementDetailView.vue'), meta: { permission: 'rd.requirement.view' } },
        { path: 'versions', name: 'version-list', component: () => import('@/views/version/VersionListView.vue'), meta: { permission: 'rd.version.view' } },
        { path: 'versions/new', name: 'version-create', component: () => import('@/views/version/VersionCreateView.vue'), meta: { permission: 'rd.version.create' } },
        { path: 'versions/:id', name: 'version-detail', component: () => import('@/views/version/VersionDetailView.vue'), meta: { permission: 'rd.version.view' } },
        { path: 'releases', name: 'release-list', component: () => import('@/views/release/ReleaseListView.vue'), meta: { permission: 'rd.release.view' } },
        { path: 'notifications', name: 'notifications', component: () => import('@/views/notification/NotificationCenterView.vue') },
        { path: 'profile', name: 'profile', component: () => import('@/views/profile/ProfileView.vue') },
        { path: 'admin/audits', name: 'audit-center', component: () => import('@/views/audit/AuditCenterView.vue'), meta: { permission: 'sys.audit.view' } },
        { path: 'admin/systems', name: 'system-catalog', component: () => import('@/views/system/SystemCatalogView.vue'), meta: { permission: 'sys.system.manage', requiresAllScope: true } },
        { path: 'admin/roles', name: 'role-management', component: () => import('@/views/system/RoleListView.vue'), meta: { permission: ['sys.role.view', 'sys.role.manage'], requiresAllScope: true } },
        { path: 'system/users', name: 'user-list', component: () => import('@/views/system/UserListView.vue'), meta: { permission: 'sys.user.view' } },
        { path: 'system/roles', redirect: { name: 'role-management' } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore(pinia)
  if (to.meta.public) {
    if (auth.isAuthenticated && !auth.initialized && !(await auth.restoreSession())) return true
    if (auth.isAuthenticated && auth.initialized) {
      return auth.mustChangePassword ? { name: 'change-password' } : { name: 'dashboard' }
    }
    return true
  }

  if (!auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (!auth.initialized && !(await auth.restoreSession())) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (auth.mustChangePassword && !to.meta.allowPasswordChangeRequired) {
    return { name: 'change-password' }
  }
  if (to.meta.permission && !auth.hasPermission(to.meta.permission)) {
    return { name: 'forbidden' }
  }
  if (to.meta.requiresAllScope && auth.user?.data_scope !== 'ALL') {
    return { name: 'forbidden' }
  }
  return true
})
