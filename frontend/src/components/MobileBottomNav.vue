<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const items = computed(() => [
  { to: '/', label: '首页', permission: 'dashboard.view' },
  { to: '/feedbacks', label: '反馈', permission: 'rd.feedback.view' },
  { to: '/requirements', label: '需求', permission: 'rd.requirement.view' },
  { to: '/versions', label: '版本', permission: 'rd.version.view' },
  { to: '/notifications', label: '消息' },
].filter((item) => !item.permission || auth.hasPermission(item.permission)))
</script>

<template>
  <nav class="bottom mobile-only" aria-label="主导航">
    <router-link v-for="item in items" :key="item.to" :to="item.to">{{ item.label }}</router-link>
  </nav>
</template>
<style scoped>
.bottom {
  position: fixed;
  right: 0;
  bottom: 0;
  left: 0;
  height: 62px;
  align-items: center;
  justify-content: space-around;
  background: #fff;
  border-top: 1px solid #e5e7eb;
  font-size: 12px;
  z-index: 20;
}

.router-link-active {
  color: #409eff;
  font-weight: 700;
}

@media (max-width: 767px) {
  .bottom {
    display: flex;
  }
}
</style>
