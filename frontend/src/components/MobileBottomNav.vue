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
    <router-link
      v-for="item in items"
      :key="item.to"
      :to="item.to"
      class="nav-tab"
      :class="{ home: item.to === '/' }"
    >
      <span class="nav-tab__icon">
        <AppIcon :name="item.icon" :size="20" />
        <span
          v-if="item.to === '/notifications' && notifications.unreadCount > 0"
          class="notification-badge"
          :aria-label="`${notifications.unreadCount} 条未读通知`"
        >
          {{ notifications.badgeText }}
        </span>
      </span>
      <span class="nav-tab__label">{{ item.label }}</span>
    </router-link>
  </nav>
</template>

<style scoped>
.bottom {
  position: fixed;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 40;
  height: calc(var(--if-bottom-nav-height) + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  align-items: stretch;
  background: rgba(255, 255, 255, 0.95);
  border-top: 1px solid var(--if-border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.nav-tab {
  display: flex;
  flex: 1 1 0;
  min-width: 0;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  color: var(--if-text-tertiary);
  font-size: 11px;
  font-weight: 500;
  transition: all 0.15s ease;
}

.nav-tab__icon {
  position: relative;
  display: inline-flex;
  padding: 2px 0;
}

.nav-tab__label {
  line-height: 1.2;
}

.notification-badge {
  position: absolute;
  top: -4px;
  left: 14px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  background: #ef4444;
  color: #ffffff;
  font-size: 10px;
  font-weight: 600;
  line-height: 16px;
  text-align: center;
  white-space: nowrap;
}

.nav-tab.router-link-exact-active,
.nav-tab.router-link-active:not(.home) {
  color: var(--if-brand-500);
  font-weight: 600;
}

@media (max-width: 767px) {
  .bottom {
    display: flex;
  }
}
</style>
