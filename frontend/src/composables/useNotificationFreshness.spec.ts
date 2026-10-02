import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useNotificationFreshness } from './useNotificationFreshness'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
const api = vi.hoisted(() => ({ count: vi.fn(), read: vi.fn(), all: vi.fn() }))
vi.mock('@/api/notifications', () => ({ getNotificationUnreadCount: api.count, markNotificationRead: api.read, markNotificationsReadAll: api.all }))
let wrapper: VueWrapper | undefined
let hidden = false
const focus = () => window.dispatchEvent(new Event('focus'))
function visibility(value: boolean) { hidden = value; document.dispatchEvent(new Event('visibilitychange')) }
function time(ms: number) { vi.setSystemTime(ms) }
function account(id: number | null) { useAuthStore().user = id === null ? null : { id } as NonNullable<ReturnType<typeof useAuthStore>['user']> }
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
async function start(id: number | null = 1) {
  account(id)
  const component = defineComponent({ setup() { useNotificationFreshness(); return () => null } })
  wrapper = mount(component)
  await flushPromises()
  return useNotificationsStore()
}
beforeEach(() => {
  setActivePinia(createPinia()); vi.resetAllMocks(); vi.useFakeTimers({ toFake: ['Date'] }); time(0)
  hidden = false
  vi.spyOn(document, 'hidden', 'get').mockImplementation(() => hidden)
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true)
  api.count.mockResolvedValue({ unread_count: 7 }); api.all.mockResolvedValue({ updated_count: 7 })
})
afterEach(() => { wrapper?.unmount(); wrapper = undefined; vi.restoreAllMocks(); vi.useRealTimers() })
it('refreshes on mount then limits focus storms to one attempt every 30 seconds', async () => {
  const store = await start(); expect(store.unreadCount).toBe(7)
  for (let i = 0; i < 20; i++) focus()
  time(29999); focus(); await flushPromises(); expect(api.count).toHaveBeenCalledTimes(1)
  time(30000); focus(); focus(); await flushPromises(); expect(api.count).toHaveBeenCalledTimes(2)
})
it('refreshes only hidden-to-visible transitions and shares the focus cooldown', async () => {
  await start(); time(30000); visibility(false); await flushPromises(); expect(api.count).toHaveBeenCalledTimes(1)
  visibility(true); focus(); await flushPromises(); expect(api.count).toHaveBeenCalledTimes(1)
  visibility(false); focus(); await flushPromises(); expect(api.count).toHaveBeenCalledTimes(2)
  visibility(false); await flushPromises(); expect(api.count).toHaveBeenCalledTimes(2)
})
it('removes listeners on unmount and logout, invalidating previous account responses', async () => {
  const old = deferred<{ unread_count: number }>(); api.count.mockReturnValueOnce(old.promise)
  const store = await start()
  const removeFocus = vi.spyOn(window, 'removeEventListener')
  const removeVisibility = vi.spyOn(document, 'removeEventListener')
  useAuthStore().reset(); expect(store.loading).toBe(false)
  expect(removeFocus).toHaveBeenCalledWith('focus', expect.any(Function))
  expect(removeVisibility).toHaveBeenCalledWith('visibilitychange', expect.any(Function))
  time(30000); focus(); visibility(true); visibility(false); await flushPromises(); expect(api.count).toHaveBeenCalledTimes(1)
  old.resolve({ unread_count: 100 }); await flushPromises(); expect(store.unreadCount).toBe(0)
  account(1); await flushPromises(); expect(api.count).toHaveBeenCalledTimes(2)
  wrapper!.unmount(); time(60000); focus(); visibility(true); visibility(false); await flushPromises()
  expect(api.count).toHaveBeenCalledTimes(2)
  expect(removeFocus.mock.calls.filter(([event]) => event === 'focus')).toHaveLength(2)
  expect(removeVisibility.mock.calls.filter(([event]) => event === 'visibilitychange')).toHaveLength(2)
})
it('resets cooldown on account switch and ignores old success/loading completion', async () => {
  const old = deferred<{ unread_count: number }>(); const latest = deferred<{ unread_count: number }>()
  api.count.mockReturnValueOnce(old.promise).mockReturnValueOnce(latest.promise)
  const store = await start(); account(2); await flushPromises(); expect(api.count).toHaveBeenCalledTimes(2)
  old.resolve({ unread_count: 99 }); await flushPromises(); expect(store.unreadCount).toBe(0); expect(store.loading).toBe(true)
  latest.resolve({ unread_count: 2 }); await flushPromises(); expect(store.unreadCount).toBe(2); expect(store.loading).toBe(false)
})
it('preserves a new account after a late old error and ends loading for the new request only', async () => {
  const old = deferred<{ unread_count: number }>(); const latest = deferred<{ unread_count: number }>()
  api.count.mockReturnValueOnce(old.promise).mockReturnValueOnce(latest.promise)
  const store = await start(); account(2); await flushPromises()
  old.reject(new Error('old offline')); await flushPromises(); expect(store.loading).toBe(true)
  latest.resolve({ unread_count: 3 }); await flushPromises(); expect(store.unreadCount).toBe(3); expect(store.loading).toBe(false)
})
it('does not resurrect unread counts when a focus response finishes after read-all', async () => {
  const store = await start(); const old = deferred<{ unread_count: number }>(); api.count.mockReturnValueOnce(old.promise)
  time(30000); focus(); await flushPromises(); await store.markAllRead(); expect(store.unreadCount).toBe(0)
  old.resolve({ unread_count: 7 }); await flushPromises(); expect(store.unreadCount).toBe(0); expect(store.loading).toBe(false)
  focus(); await flushPromises(); expect(api.count).toHaveBeenCalledTimes(2)
  time(60000); api.count.mockResolvedValue({ unread_count: 1 }); focus(); await flushPromises(); expect(store.unreadCount).toBe(1)
})
it('keeps failed attempts cooldown limited and preserves the previous badge', async () => {
  const store = await start(); api.count.mockRejectedValueOnce(new Error('offline'))
  time(30000); focus(); await flushPromises(); expect(store.unreadCount).toBe(7); expect(store.loading).toBe(false)
  focus(); time(59999); focus(); await flushPromises(); expect(api.count).toHaveBeenCalledTimes(2)
  time(60000); focus(); await flushPromises(); expect(api.count).toHaveBeenCalledTimes(3)
})
it('does not request while logged out or offline, and resumes without an obsolete cooldown', async () => {
  await start(null); focus(); await flushPromises(); expect(api.count).not.toHaveBeenCalled()
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false); account(1); focus(); await flushPromises(); expect(api.count).not.toHaveBeenCalled()
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true); focus(); await flushPromises(); expect(api.count).toHaveBeenCalledTimes(1)
})
