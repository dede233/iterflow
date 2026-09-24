<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { listNotifications, markNotificationRead } from '@/api/notifications'
import type { NotificationItem } from '@/types/domain'

const router = useRouter()
const rows = ref<NotificationItem[]>([])
const pendingId = ref<number | null>(null)

function notificationTarget(notification: NotificationItem): string | null {
  if (notification.entity_type === 'RELEASE') return '/releases'
  if (notification.entity_id == null) return null

  switch (notification.entity_type) {
    case 'FEEDBACK':
      return `/feedbacks/${notification.entity_id}`
    case 'REQUIREMENT':
      return `/requirements/${notification.entity_id}`
    case 'VERSION':
      return `/versions/${notification.entity_id}`
    default:
      return null
  }
}

async function load(): Promise<void> {
  rows.value = await listNotifications()
}

async function openNotification(notification: NotificationItem): Promise<void> {
  if (pendingId.value !== null) return
  pendingId.value = notification.id
  try {
    await markNotificationRead(notification.id)
    const target = notificationTarget(notification)
    if (target) {
      await router.push(target)
    } else {
      await load()
    }
  } catch {
    ElMessage.error('通知操作失败，请重试')
  } finally {
    pendingId.value = null
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="page">
    <div class="page-title">通知中心</div>
    <div class="cards">
      <el-card v-for="notification in rows" :key="notification.id" :class="{ unread: !notification.read_at }">
        <button
          class="notification-action"
          :class="{ navigable: notificationTarget(notification) !== null }"
          type="button"
          :disabled="pendingId !== null"
          @click="openNotification(notification)"
        >
          <b>{{ notification.title }}</b>
          <p>{{ notification.content }}</p>
          <small>{{ notification.created_at }}</small>
        </button>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.cards { display: grid; gap: 10px; }
.unread { border-left: 4px solid #409eff; }
.notification-action { display: block; width: 100%; border: 0; padding: 0; background: transparent; color: inherit; text-align: left; font: inherit; cursor: pointer; }
.notification-action:disabled { cursor: wait; }
.notification-action.navigable:not(:disabled):hover { color: var(--el-color-primary); }
.notification-action:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: 4px; }
</style>
