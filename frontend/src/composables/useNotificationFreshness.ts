import { onBeforeUnmount, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'

const COOLDOWN_MS = 30_000

/** Refresh the shared badge on resume; no timer or background polling. */
export function useNotificationFreshness(): void {
  const auth = useAuthStore()
  const notifications = useNotificationsStore()
  let mounted = false
  let listening = false
  let wasHidden = false
  let lastAttempt: number | null = null

  function refresh(): void {
    if (!mounted || !auth.user || document.hidden || !navigator.onLine) return
    const now = Date.now()
    if (lastAttempt !== null && now - lastAttempt < COOLDOWN_MS) return
    lastAttempt = now
    // Failure preserves the store's previous count and remains cooldown limited.
    void notifications.refreshUnreadCount().catch(() => {})
  }

  function visibilityChanged(): void {
    const hidden = document.hidden
    const resumed = wasHidden && !hidden
    wasHidden = hidden
    if (resumed) refresh()
  }

  function stop(): void {
    if (!listening) return
    window.removeEventListener('focus', refresh)
    document.removeEventListener('visibilitychange', visibilityChanged)
    listening = false
  }

  function start(): void {
    stop()
    if (!mounted || !auth.user) return
    wasHidden = document.hidden
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', visibilityChanged)
    listening = true
    refresh()
  }

  watch(() => auth.user?.id, () => {
    lastAttempt = null
    start()
  }, { flush: 'sync' })
  onMounted(() => { mounted = true; start() })
  onBeforeUnmount(() => { mounted = false; stop() })
}
