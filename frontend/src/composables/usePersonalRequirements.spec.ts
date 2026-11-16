import { effectScope, reactive } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { listRequirements } from '@/api/requirements'
import { usePersonalRequirements } from './usePersonalRequirements'
import type { RequirementPage } from '@/types/domain'

vi.mock('@/api/requirements', () => ({ listRequirements: vi.fn() }))
const list = vi.mocked(listRequirements)
const page = (title: string, total = 1) => ({ items: [{ id: 1, title, requirement_no: 'REQ-20261111-0001', updated_at: '2026-11-11T10:00:00Z' }], total }) as RequirementPage
const deferred = <T>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r }); return { promise, resolve } }

describe('personal requirement work queue', () => {
  beforeEach(() => list.mockReset())
  it('loads three bounded lists scoped to the current participant and displays server personal totals', async () => {
    list.mockResolvedValue(page('待处理', 7))
    const scope = effectScope()
    const queue = scope.run(() => usePersonalRequirements(() => [43, true, '43:view']))!
    await flushPromises()
    expect(list.mock.calls.map(([params]) => params)).toEqual([
      { page: 1, page_size: 3, status: 'DRAFT', participant_id: 43, participant_role: 'CONFIRM' },
      { page: 1, page_size: 3, status: 'CONFIRMED', participant_id: 43, participant_role: 'DEVELOP' },
      { page: 1, page_size: 3, status: 'TESTING', participant_id: 43, participant_role: 'ACCEPT' },
    ])
    expect(queue.groups.map(g => g.total)).toEqual([7, 7, 7])
    expect(queue.groups.every(g => !g.loading && !g.failed)).toBe(true)
    scope.stop()
  })
  it('does not query without permission or a valid account, and discards pending results when access changes', async () => {
    const state = reactive({ id: undefined as number | undefined, allowed: false, key: 'none' })
    const pending = deferred<RequirementPage>()
    list.mockReturnValue(pending.promise)
    const scope = effectScope()
    const queue = scope.run(() => usePersonalRequirements(() => [state.id, state.allowed, state.key]))!
    expect(list).not.toHaveBeenCalled()
    state.id = 4; state.allowed = true
    expect(list).toHaveBeenCalledTimes(3)
    state.allowed = false
    pending.resolve(page('旧账号数据'))
    await flushPromises()
    expect(queue.groups.every(g => g.items.length === 0 && g.total === 0 && !g.loading)).toBe(true)
    scope.stop()
  })
  it('ignores the previous account and unmounted requests', async () => {
    const state = reactive({ id: 4 })
    const old = deferred<RequirementPage>(), current = deferred<RequirementPage>()
    list.mockImplementation(params => params?.participant_id === 4 ? old.promise : current.promise)
    const scope = effectScope()
    const queue = scope.run(() => usePersonalRequirements(() => [state.id, true, String(state.id)]))!
    state.id = 5
    current.resolve(page('当前账号'))
    await flushPromises()
    old.resolve(page('旧账号'))
    await flushPromises()
    expect(queue.groups.map(g => g.items[0]?.title)).toEqual(['当前账号', '当前账号', '当前账号'])
    scope.stop()
    expect(queue.groups.every(g => g.items.length === 0)).toBe(true)
    queue.retry('confirm')
    expect(list).toHaveBeenCalledTimes(6)
  })
  it('keeps failed and empty states distinct and retries only the failed group', async () => {
    list.mockImplementation(params => params?.participant_role === 'ACCEPT' ? Promise.reject(new Error('offline')) : Promise.resolve({ items: [], total: 0 } as unknown as RequirementPage))
    const scope = effectScope()
    const queue = scope.run(() => usePersonalRequirements(() => [43, true, '43']))!
    await flushPromises()
    expect(queue.groups.map(g => g.failed)).toEqual([false, false, true])
    list.mockResolvedValue(page('验收'))
    queue.retry('accept')
    await flushPromises()
    expect(list).toHaveBeenCalledTimes(4)
    expect(queue.groups[2]?.failed).toBe(false)
    expect(queue.groups[2]?.items[0]?.title).toBe('验收')
    scope.stop()
  })
})
