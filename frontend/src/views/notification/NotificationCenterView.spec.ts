import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import type { NotificationItem } from '@/types/domain'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  count: vi.fn(),
  all: vi.fn(),
  markRead: vi.fn(),
  push: vi.fn(),
  error: vi.fn(),
}))

vi.mock('@/api/notifications', () => ({
  listNotifications: mocks.list,
  markNotificationRead: mocks.markRead,
  getNotificationUnreadCount: mocks.count,
  markNotificationsReadAll: mocks.all,
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))
vi.mock('element-plus', () => ({ ElMessage: { error: mocks.error } }))

import NotificationCenterView from './NotificationCenterView.vue'

const baseNotification: NotificationItem = {
  id: 1,
  type: 'FEEDBACK',
  title: '反馈 FB-001 已上线',
  content: '版本已发布',
  entity_type: 'FEEDBACK',
  entity_id: 123,
  read_at: null,
  created_at: '2026-09-24T00:00:00Z',
}

function notification(overrides: Partial<NotificationItem> = {}): NotificationItem {
  return { ...baseNotification, ...overrides }
}

async function view(item: NotificationItem) {
  mocks.list.mockResolvedValue([item])
  const wrapper = mount(NotificationCenterView, {
    global: {
      plugins: [createPinia()],
      directives: { loading: () => {} },
      stubs: { 'el-button': { template: '<button><slot /></button>' } },
    },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.count.mockResolvedValue({ unread_count: 7 })
  mocks.all.mockResolvedValue({ updated_count: 7 })
  mocks.markRead.mockResolvedValue({ ok: true })
  mocks.push.mockResolvedValue(undefined)
})

describe('notification business navigation', () => {
  it.each([
    ['FEEDBACK', 123, '/feedbacks/123'],
    ['REQUIREMENT', 456, '/requirements/456'],
    ['VERSION', 789, '/versions/789'],
    ['RELEASE', 123, '/releases/123'],
    ['RELEASE', null, '/releases'],
  ])('marks %s notification (id %s) read before navigating to %s', async (entityType, entityId, target) => {
    const wrapper = await view(notification({ entity_type: entityType, entity_id: entityId }))
    mocks.markRead.mockImplementation(async () => {
      expect(mocks.push).not.toHaveBeenCalled()
      return { ok: true }
    })

    await wrapper.get('.notification-card').trigger('click')
    await flushPromises()

    expect(mocks.markRead).toHaveBeenCalledWith(1)
    expect(mocks.push).toHaveBeenCalledWith(target)
    expect(wrapper.text()).toContain('6 条未读')
    expect(mocks.markRead.mock.invocationCallOrder[0]).toBeLessThan(mocks.push.mock.invocationCallOrder[0]!)
    expect(wrapper.get('.notification-card').classes()).toContain('navigable')
  })

  it.each([
    ['SYSTEM', null, null],
    ['FEEDBACK', 'UNKNOWN', 123],
    ['REQUIREMENT without an id', 'REQUIREMENT', null],
  ])('only marks %s read', async (_, entityType, entityId) => {
    const wrapper = await view(notification({ entity_type: entityType, entity_id: entityId }))

    await wrapper.get('.notification-card').trigger('click')
    await flushPromises()

    expect(mocks.markRead).toHaveBeenCalledWith(1)
    expect(mocks.push).not.toHaveBeenCalled()
    expect(mocks.list).toHaveBeenCalledTimes(2)
    expect(wrapper.get('.notification-card').classes()).not.toContain('navigable')
  })

  it('still navigates when the notification was already read', async () => {
    const wrapper = await view(notification({ read_at: '2026-09-24T01:00:00Z' }))

    await wrapper.get('.notification-card').trigger('click')
    await flushPromises()

    expect(mocks.push).toHaveBeenCalledWith('/feedbacks/123')
    expect(wrapper.text()).toContain('7 条未读')
  })

  it('does not navigate when marking read fails', async () => {
    const wrapper = await view(notification())
    mocks.markRead.mockRejectedValue(new Error('network failed'))

    await wrapper.get('.notification-card').trigger('click')
    await flushPromises()

    expect(mocks.push).not.toHaveBeenCalled()
    expect(mocks.error).toHaveBeenCalledWith('通知操作失败，请重试')
  })
})


describe('notification totals and read all', () => {
  it('uses the true count even with only one loaded row', async () => {
    mocks.count.mockResolvedValue({ unread_count: 125 })
    const wrapper = await view(notification())
    expect(wrapper.text()).toContain('125 条未读')
    expect(wrapper.findAll('.notification-card')).toHaveLength(1)
    expect(wrapper.text()).toContain('全部已读')
  })
  it('hides read all for zero unread', async () => {
    mocks.count.mockResolvedValue({ unread_count: 0 })
    const wrapper = await view(notification({ read_at: '2026-01-01T00:00:00Z' }))
    expect(wrapper.text()).toContain('0 条未读')
    expect(wrapper.text()).not.toContain('全部已读')
  })
  it('clears badges and loaded unread rows after read all succeeds', async () => {
    const wrapper = await view(notification())
    await wrapper.findAll('button').find(button => button.text() === '全部已读')!.trigger('click')
    await flushPromises()
    expect(mocks.all).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('0 条未读')
    expect(wrapper.findAll('.unread-dot')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('全部已读')
    expect(mocks.push).not.toHaveBeenCalled()
  })
  it('preserves totals and unread rows on read all failure', async () => {
    mocks.all.mockRejectedValue(new Error('failed'))
    const wrapper = await view(notification())
    await wrapper.findAll('button').find(button => button.text() === '全部已读')!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('7 条未读')
    expect(wrapper.get('.notification-card').classes()).toContain('unread')
    expect(mocks.error).toHaveBeenCalledWith('通知操作失败，请重试')
  })
  it('does not block the notification list if count fails', async () => {
    mocks.count.mockRejectedValue(new Error('failed'))
    const wrapper = await view(notification())
    expect(wrapper.findAll('.notification-card')).toHaveLength(1)
    expect(wrapper.text()).toContain('0 条未读')
  })
  it('updates count before navigation, and a failed read leaves it intact', async () => {
    const wrapper = await view(notification())
    mocks.push.mockImplementation(async () => { expect(wrapper.text()).toContain('6 条未读') })
    await wrapper.get('.notification-card').trigger('click')
    await flushPromises()
    expect(mocks.push).toHaveBeenCalled()
  })
})
