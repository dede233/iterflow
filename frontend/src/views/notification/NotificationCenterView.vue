<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { listNotifications, markNotificationRead } from '@/api/notifications'
import type { NotificationItem } from '@/types/domain'
import PageHeader from '@/components/ui/PageHeader.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import { formatLocalDateTime } from '@/utils/dates'

const router = useRouter()
const rows = ref<NotificationItem[]>([])
const pendingId = ref<number | null>(null)
const loading = ref(false)
const failed = ref(false)
const unreadCount = computed(() => rows.value.filter((item) => !item.read_at).length)

function notificationIcon(entityType: string | null): string {
  return ({ FEEDBACK: 'feedback', REQUIREMENT: 'requirement', VERSION: 'version', RELEASE: 'release' } as Record<string, string>)[entityType ?? ''] ?? 'bell'
}

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
  loading.value = true
  failed.value = false
  try {
    rows.value = await listNotifications()
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

async function openNotification(notification: NotificationItem): Promise<void> {
  if (pendingId.value !== null) return
  pendingId.value = notification.id
  try {
    await markNotificationRead(notification.id)
    notification.read_at = new Date().toISOString()
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
  <section class="page">
    <PageHeader title="通知中心" description="查看与你有关的反馈、需求和版本动态。" eyebrow="工作台">
      <template #actions><span class="unread-count">{{ unreadCount }} 条未读</span></template>
    </PageHeader>
    <ErrorState v-if="failed" title="通知加载失败" description="请检查网络后重试。" retry-label="重新加载" @retry="load" />
    <div v-else v-loading="loading" class="cards">
        <button
          v-for="notification in rows"
          :key="notification.id"
          class="notification-card"
          :class="{ unread: !notification.read_at, navigable: notificationTarget(notification) !== null }"
          type="button"
          :disabled="pendingId !== null"
          :aria-busy="pendingId === notification.id"
          @click="openNotification(notification)"
        >
          <span class="notification-icon"><AppIcon :name="notificationIcon(notification.entity_type)" :size="18" /></span>
          <span class="notification-body">
            <span class="notification-top"><strong>{{ notification.title }}</strong><span class="notification-time">{{ formatLocalDateTime(notification.created_at) }}</span></span>
            <span class="notification-content">{{ notification.content }}</span>
            <span v-if="pendingId === notification.id" class="notification-pending">正在打开…</span>
          </span>
          <span v-if="!notification.read_at" class="unread-dot" aria-label="未读" />
        </button>
      <EmptyState v-if="!loading && !rows.length" description="暂无通知" />
    </div>
  </section>
</template>

<style scoped>
.unread-count { display: inline-flex; align-items: center; min-height: 30px; padding: 0 12px; border-radius: 999px; background: var(--if-brand-50); color: var(--if-brand-700); font-size: 12px; font-weight: 700; }
.cards { display: grid; gap: 10px; max-width: 980px; }
.notification-card { display: flex; align-items: flex-start; gap: 14px; width: 100%; min-width: 0; padding: 18px; border: 1px solid var(--if-border); border-radius: var(--if-radius); background: var(--if-bg-surface); color: var(--if-text-1); box-shadow: var(--if-shadow-sm); font: inherit; text-align: left; cursor: pointer; }
.notification-card.unread { border-left: 3px solid var(--if-brand-500); background: linear-gradient(100deg, var(--if-brand-50), #fff 24%); }
.notification-card:hover:not(:disabled) { border-color: var(--if-brand-100); box-shadow: var(--if-shadow); }
.notification-card:disabled { cursor: wait; }
.notification-icon { display: grid; place-items: center; flex: 0 0 34px; height: 34px; border-radius: 10px; background: var(--if-brand-50); color: var(--if-brand-700); font-size: 13px; font-weight: 800; }
.notification-body { display: grid; gap: 5px; min-width: 0; flex: 1; }
.notification-top { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.notification-top strong { font-size: 14px; overflow-wrap: anywhere; }
.notification-time { flex-shrink: 0; color: var(--if-text-3); font-size: 12px; }
.notification-content { color: var(--if-text-2); font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }
.notification-pending { color: var(--if-brand-600); font-size: 12px; }
.unread-dot { flex: 0 0 7px; width: 7px; height: 7px; margin-top: 7px; border-radius: 50%; background: var(--if-brand-500); }
@media (max-width: 767px) { .notification-card { gap: 10px; padding: 14px; } .notification-top { display: grid; gap: 4px; } .notification-time { order: -1; } }
</style>
