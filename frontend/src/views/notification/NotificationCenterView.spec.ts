import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { NotificationItem } from '@/types/domain'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  markRead: vi.fn(),
  push: vi.fn(),
  error: vi.fn(),
}))

vi.mock('@/api/notifications', () => ({
  listNotifications: mocks.list,
  markNotificationRead: mocks.markRead,
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
      stubs: { 'el-card': { template: '<article><slot /></article>' } },
    },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.markRead.mockResolvedValue({ ok: true })
  mocks.push.mockResolvedValue(undefined)
})

describe('notification business navigation', () => {
  it.each([
    ['FEEDBACK', 123, '/feedbacks/123'],
    ['REQUIREMENT', 456, '/requirements/456'],
    ['VERSION', 789, '/versions/789'],
    ['RELEASE', null, '/releases'],
  ])('marks %s notification (id %s) read before navigating to %s', async (entityType, entityId, target) => {
    const wrapper = await view(notification({ entity_type: entityType, entity_id: entityId }))
    mocks.markRead.mockImplementation(async () => {
      expect(mocks.push).not.toHaveBeenCalled()
      return { ok: true }
    })

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(mocks.markRead).toHaveBeenCalledWith(1)
    expect(mocks.push).toHaveBeenCalledWith(target)
    expect(mocks.markRead.mock.invocationCallOrder[0]).toBeLessThan(mocks.push.mock.invocationCallOrder[0]!)
    expect(wrapper.get('button').classes()).toContain('navigable')
  })

  it.each([
    ['SYSTEM', null, null],
    ['FEEDBACK', 'UNKNOWN', 123],
    ['REQUIREMENT without an id', 'REQUIREMENT', null],
  ])('only marks %s read', async (_, entityType, entityId) => {
    const wrapper = await view(notification({ entity_type: entityType, entity_id: entityId }))

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(mocks.markRead).toHaveBeenCalledWith(1)
    expect(mocks.push).not.toHaveBeenCalled()
    expect(mocks.list).toHaveBeenCalledTimes(2)
    expect(wrapper.get('button').classes()).not.toContain('navigable')
  })

  it('still navigates when the notification was already read', async () => {
    const wrapper = await view(notification({ read_at: '2026-09-24T01:00:00Z' }))

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(mocks.push).toHaveBeenCalledWith('/feedbacks/123')
  })

  it('does not navigate when marking read fails', async () => {
    const wrapper = await view(notification())
    mocks.markRead.mockRejectedValue(new Error('network failed'))

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(mocks.push).not.toHaveBeenCalled()
    expect(mocks.error).toHaveBeenCalledWith('通知操作失败，请重试')
  })
})
