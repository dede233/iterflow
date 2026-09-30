import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useNotificationsStore } from './notifications'
import { useAuthStore } from './auth'

const api = vi.hoisted(() => ({ count: vi.fn(), read: vi.fn(), all: vi.fn() }))
vi.mock('@/api/notifications', () => ({ getNotificationUnreadCount: api.count, markNotificationRead: api.read, markNotificationsReadAll: api.all }))

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.resetAllMocks()
  api.count.mockResolvedValue({ unread_count: 7 })
  api.read.mockResolvedValue({ ok: true })
  api.all.mockResolvedValue({ updated_count: 7 })
})

describe('shared notification state', () => {
  it('starts empty, loads true totals and refreshes', async () => {
    const store = useNotificationsStore()
    expect(store.unreadCount).toBe(0)
    await store.refreshUnreadCount()
    expect(store.unreadCount).toBe(7)
    api.count.mockResolvedValue({ unread_count: 125 })
    await store.refreshUnreadCount()
    expect(store.unreadCount).toBe(125)
    expect(store.badgeText).toBe('99+')
    expect(store.loading).toBe(false)
  })
  it('deduplicates simultaneous count requests', async () => {
    const pending = deferred<{ unread_count: number }>()
    api.count.mockReturnValue(pending.promise)
    const store = useNotificationsStore()
    const first = store.refreshUnreadCount()
    const second = store.refreshUnreadCount()
    expect(store.loading).toBe(true)
    expect(api.count).toHaveBeenCalledTimes(1)
    pending.resolve({ unread_count: 2 })
    await Promise.all([first, second])
    expect(store.unreadCount).toBe(2)
  })
  it('decrements only unread items and never below zero', async () => {
    const store = useNotificationsStore()
    store.unreadCount = 1
    await store.markRead(1, true)
    expect(store.unreadCount).toBe(0)
    await store.markRead(2, true)
    expect(store.unreadCount).toBe(0)
    store.unreadCount = 3
    await store.markRead(1, false)
    expect(store.unreadCount).toBe(3)
  })
  it('deduplicates concurrent reads of the same notification', async () => {
    const pending = deferred<{ ok: boolean }>()
    api.read.mockReturnValue(pending.promise)
    const store = useNotificationsStore()
    store.unreadCount = 2
    const first = store.markRead(1, true)
    const second = store.markRead(1, true)
    pending.resolve({ ok: true })
    await Promise.all([first, second])
    expect(store.unreadCount).toBe(1)
    expect(api.read).toHaveBeenCalledTimes(1)
  })
  it('preserves count after single read failure', async () => {
    api.read.mockRejectedValue(new Error('failed'))
    const store = useNotificationsStore()
    store.unreadCount = 2
    await expect(store.markRead(1, true)).rejects.toThrow('failed')
    expect(store.unreadCount).toBe(2)
  })
  it('marks all read once while pending and clears only after success', async () => {
    const pending = deferred<{ updated_count: number }>()
    api.all.mockReturnValue(pending.promise)
    const store = useNotificationsStore()
    store.unreadCount = 125
    const first = store.markAllRead()
    const second = store.markAllRead()
    expect(store.markingAllRead).toBe(true)
    expect(store.unreadCount).toBe(125)
    expect(api.all).toHaveBeenCalledTimes(1)
    pending.resolve({ updated_count: 125 })
    await Promise.all([first, second])
    expect(store.unreadCount).toBe(0)
    expect(store.markingAllRead).toBe(false)
  })
  it('read-all failure preserves count and allows retry', async () => {
    api.all.mockRejectedValueOnce(new Error('failed'))
    const store = useNotificationsStore()
    store.unreadCount = 3
    await expect(store.markAllRead()).rejects.toThrow('failed')
    expect(store.unreadCount).toBe(3)
    expect(store.markingAllRead).toBe(false)
    await store.markAllRead()
    expect(store.unreadCount).toBe(0)
  })
  it('count failure preserves last count and ends loading', async () => {
    api.count.mockRejectedValue(new Error('failed'))
    const store = useNotificationsStore()
    await expect(store.refreshUnreadCount()).rejects.toThrow('failed')
    expect(store.unreadCount).toBe(0)
    store.unreadCount = 3
    await expect(store.refreshUnreadCount()).rejects.toThrow('failed')
    expect(store.unreadCount).toBe(3)
    expect(store.loading).toBe(false)
  })
  it.each(['single', 'all'])('ignores an old count response after %s read', async (kind) => {
    const pending = deferred<{ unread_count: number }>()
    api.count.mockReturnValue(pending.promise)
    const store = useNotificationsStore()
    store.unreadCount = 2
    const refresh = store.refreshUnreadCount()
    if (kind === 'single') await store.markRead(1, true)
    else await store.markAllRead()
    pending.resolve({ unread_count: 2 })
    await refresh
    expect(store.unreadCount).toBe(kind === 'single' ? 1 : 0)
  })
  it('clears state on logout and ignores previous session responses', async () => {
    const pending = deferred<{ unread_count: number }>()
    api.count.mockReturnValue(pending.promise)
    const auth = useAuthStore()
    // Only the account identity matters to session isolation.
    auth.user = { id: 1 } as NonNullable<typeof auth.user>
    const store = useNotificationsStore()
    store.unreadCount = 7
    const refresh = store.refreshUnreadCount()
    auth.reset()
    expect(store.unreadCount).toBe(0)
    pending.resolve({ unread_count: 7 })
    await refresh
    expect(store.unreadCount).toBe(0)
  })
  it.each(['single', 'all'])('ignores a previous account %s-read response', async kind => {
    const pending = deferred<{ ok: boolean; updated_count: number }>()
    api.read.mockReturnValue(pending.promise)
    api.all.mockReturnValue(pending.promise)
    const auth = useAuthStore()
    auth.user = { id: 1 } as NonNullable<typeof auth.user>
    const store = useNotificationsStore()
    store.unreadCount = 7
    const read = kind === 'single' ? store.markRead(1, true) : store.markAllRead()
    auth.user = { id: 2 } as NonNullable<typeof auth.user>
    store.unreadCount = 2
    pending.resolve({ ok: true, updated_count: 7 })
    await read
    expect(store.unreadCount).toBe(2)
    expect(store.markingAllRead).toBe(false)
  })

})
