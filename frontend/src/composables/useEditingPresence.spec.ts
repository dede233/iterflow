import { defineComponent, h } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const calls = vi.hoisted(() => ({
  start: vi.fn(),
  heartbeat: vi.fn(),
  end: vi.fn(),
}))

vi.mock('@/api/editing', () => ({
  startEditing: calls.start,
  editingHeartbeat: calls.heartbeat,
  endEditing: calls.end,
}))

import { useEditingPresence } from './useEditingPresence'

type Presence = ReturnType<typeof useEditingPresence>
let wrappers: ReturnType<typeof mount>[] = []

function setup(): Presence {
  let presence!: Presence
  const host = defineComponent({
    setup() {
      presence = useEditingPresence('REQUIREMENT', 7)
      return () => h('div')
    },
  })
  wrappers.push(mount(host))
  return presence
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}

const alice = { user_id: 1, display_name: '测试用户A', active_at: '2026-09-29T00:00:00Z' }
const bob = { user_id: 2, display_name: '测试用户B', active_at: '2026-09-29T00:01:00Z' }

beforeEach(() => {
  vi.useFakeTimers()
  vi.clearAllMocks()
  calls.start.mockResolvedValue({ existing_editor: null })
  calls.heartbeat.mockResolvedValue({ ok: true, existing_editor: null })
  calls.end.mockResolvedValue({ ok: true })
})

afterEach(() => {
  for (const wrapper of wrappers) wrapper.unmount()
  wrappers = []
  vi.clearAllTimers()
  vi.useRealTimers()
})

describe('useEditingPresence', () => {
  it('starts once, creates one timer, and heartbeats after 120 seconds', async () => {
    const presence = setup()
    await presence.start()
    expect(calls.start).toHaveBeenCalledExactlyOnceWith('REQUIREMENT', 7)
    expect(presence.isActive.value).toBe(true)
    expect(presence.isStarting.value).toBe(false)
    expect(vi.getTimerCount()).toBe(1)
    await vi.advanceTimersByTimeAsync(119_999)
    expect(calls.heartbeat).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(calls.heartbeat).toHaveBeenCalledExactlyOnceWith('REQUIREMENT', 7)
  })

  it('never overlaps heartbeats while a request is pending', async () => {
    const pending = deferred<{ ok: boolean; existing_editor: null }>()
    calls.heartbeat.mockReturnValueOnce(pending.promise)
    const presence = setup()
    await presence.start()
    await vi.advanceTimersByTimeAsync(240_000)
    expect(calls.heartbeat).toHaveBeenCalledTimes(1)
    pending.resolve({ ok: true, existing_editor: null })
    await flushPromises()
    await vi.advanceTimersByTimeAsync(120_000)
    expect(calls.heartbeat).toHaveBeenCalledTimes(2)
  })

  it('shows an existing editor from start and updates it from heartbeat', async () => {
    calls.start.mockResolvedValueOnce({ existing_editor: alice })
    calls.heartbeat.mockResolvedValueOnce({ ok: false, existing_editor: bob })
    const presence = setup()
    await presence.start()
    expect(presence.existingEditor.value).toEqual(alice)
    await vi.advanceTimersByTimeAsync(120_000)
    expect(presence.existingEditor.value).toEqual(bob)
  })

  it('stops its timer, calls end, and does not heartbeat after stop', async () => {
    const presence = setup()
    await presence.start()
    await presence.stop()
    expect(calls.end).toHaveBeenCalledExactlyOnceWith('REQUIREMENT', 7)
    expect(presence.isActive.value).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
    await vi.advanceTimersByTimeAsync(240_000)
    expect(calls.heartbeat).not.toHaveBeenCalled()
  })

  it('keeps editing available when start fails', async () => {
    calls.start.mockRejectedValueOnce(new Error('offline'))
    const presence = setup()
    await expect(presence.start()).resolves.toBeUndefined()
    expect(presence.isActive.value).toBe(true)
    expect(presence.isStarting.value).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
    await presence.stop()
    expect(calls.end).not.toHaveBeenCalled()
  })

  it('retains the session after heartbeat failure and tolerates end failure', async () => {
    calls.heartbeat.mockRejectedValueOnce(new Error('offline'))
    calls.end.mockRejectedValueOnce(new Error('offline'))
    const presence = setup()
    await presence.start()
    await vi.advanceTimersByTimeAsync(120_000)
    expect(presence.isActive.value).toBe(true)
    await vi.advanceTimersByTimeAsync(120_000)
    expect(calls.heartbeat).toHaveBeenCalledTimes(2)
    await expect(presence.stop()).resolves.toBeUndefined()
  })

  it('cleans up a pending start on rapid close and starts fresh on reopen', async () => {
    const pending = deferred<{ existing_editor: null }>()
    calls.start.mockReturnValueOnce(pending.promise)
    const presence = setup()
    const first = presence.start()
    const closed = presence.stop()
    const reopened = presence.start()
    pending.resolve({ existing_editor: null })
    await Promise.all([first, closed, reopened])
    expect(calls.start).toHaveBeenCalledTimes(2)
    expect(calls.end).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(1)
    await presence.stop()
    expect(calls.end).toHaveBeenCalledTimes(2)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('waits for an in-flight heartbeat before ending, including on unmount', async () => {
    const pending = deferred<{ ok: boolean; existing_editor: null }>()
    calls.heartbeat.mockReturnValueOnce(pending.promise)
    const presence = setup()
    await presence.start()
    await vi.advanceTimersByTimeAsync(120_000)
    wrappers[0]!.unmount()
    expect(vi.getTimerCount()).toBe(0)
    expect(calls.end).not.toHaveBeenCalled()
    pending.resolve({ ok: true, existing_editor: null })
    await flushPromises()
    expect(calls.end).toHaveBeenCalledOnce()
    expect(presence.existingEditor.value).toBeNull()
  })
})
