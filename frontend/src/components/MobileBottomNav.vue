<script setup lang="ts">
import { computed } from 'vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'

const auth = useAuthStore()
const notifications = useNotificationsStore()
const items = computed(() => [
  { to: '/', label: '首页', icon: 'home', permission: 'dashboard.view' },
  { to: '/feedbacks', label: '反馈', icon: 'feedback', permission: 'rd.feedback.view' },
  { to: '/requirements', label: '需求', icon: 'requirement', permission: 'rd.requirement.view' },
  { to: '/versions', label: '版本', icon: 'version', permission: 'rd.version.view' },
  { to: '/notifications', label: '消息', icon: 'bell' },
  { to: '/profile', label: '我的', icon: 'user' },
].filter((item) => !item.permission || auth.hasPermission(item.permission)))
</script>

<template>
  <nav class="bottom mobile-only" aria-label="主导航">
    <router-link v-for="item in items" :key="item.to" :to="item.to" :class="{ home: item.to === '/' }">
      <span class="nav-icon"><AppIcon :name="item.icon" :size="20" /><span v-if="item.to === '/notifications' && notifications.unreadCount > 0" class="notification-badge" :aria-label="`${notifications.unreadCount} 条未读通知`">{{ notifications.badgeText }}</span></span>
      <span>{{ item.label }}</span>
    </router-link>
  </nav>
</template>
<style scoped>
.nav-icon { position: relative; display: inline-flex; }
.notification-badge { position: absolute; top: -7px; left: 12px; min-width: 16px; padding: 0 4px; border-radius: 999px; background: var(--if-brand-500); color: #fff; font-size: 10px; line-height: 16px; text-align: center; white-space: nowrap; }
.bottom {
  position: fixed;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 40;
  height: calc(var(--if-bottom-nav-height) + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  align-items: stretch;
  background: rgba(255, 255, 255, .96);
  border-top: 1px solid var(--if-border);
  backdrop-filter: blur(8px);
}

.bottom a {
  display: flex;
  flex: 1 1 0;
  min-width: 0;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  color: var(--if-text-3);
  font-size: 11px;
  font-weight: 500;
}

.bottom a.router-link-exact-active,
.bottom a.router-link-active:not(.home) {
  color: var(--if-brand-500);
  font-weight: 700;
}

@media (max-width: 767px) {
  .bottom {
    display: flex;
  }
}
</style>
