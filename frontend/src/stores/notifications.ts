import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { getNotificationUnreadCount, markNotificationRead, markNotificationsReadAll } from '@/api/notifications'
import { useAuthStore } from './auth'

export const useNotificationsStore = defineStore('notifications', () => {
  const auth = useAuthStore()
  const unreadCount = ref(0)
  const loading = ref(false)
  const markingAllRead = ref(false)
  const badgeText = computed(() => unreadCount.value > 99 ? '99+' : String(unreadCount.value))
  let generation = 0
  let session = 0
  let refresh: Promise<void> | null = null
  let readAll: Promise<void> | null = null
  const reads = new Map<number, Promise<void>>()

  watch(() => auth.user?.id, () => {
    generation++
    session++
    unreadCount.value = 0
    loading.value = false
    markingAllRead.value = false
    refresh = null
    readAll = null
    reads.clear()
  }, { flush: 'sync' })

  function refreshUnreadCount(): Promise<void> {
    if (refresh) return refresh
    const version = generation
    loading.value = true
    const request = getNotificationUnreadCount().then(({ unread_count }) => {
      if (version === generation) unreadCount.value = unread_count
    }).finally(() => {
      if (refresh === request) {
        loading.value = false
        refresh = null
      }
    })
    refresh = request
    return request
  }

  function markRead(id: number, wasUnread: boolean): Promise<void> {
    const pending = reads.get(id)
    if (pending) return pending
    const currentSession = session
    const request = markNotificationRead(id).then(() => {
      if (session === currentSession) {
        generation++
        if (wasUnread) unreadCount.value = Math.max(0, unreadCount.value - 1)
      }
    }).finally(() => {
      if (reads.get(id) === request) reads.delete(id)
    })
    reads.set(id, request)
    return request
  }

  function markAllRead(): Promise<void> {
    if (readAll) return readAll
    const currentSession = session
    markingAllRead.value = true
    const request = markNotificationsReadAll().then(() => {
      if (session === currentSession) {
        generation++
        unreadCount.value = 0
      }
    }).finally(() => {
      if (readAll === request) {
        markingAllRead.value = false
        readAll = null
      }
    })
    readAll = request
    return request
  }

  return { unreadCount, loading, markingAllRead, badgeText, refreshUnreadCount, markRead, markAllRead }
})
