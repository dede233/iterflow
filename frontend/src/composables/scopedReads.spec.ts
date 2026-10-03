import { effectScope, reactive } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useScopedLookup } from './useScopedLookup'
import { useScopedSearch } from './useScopedSearch'
function deferred<T>() { let resolve!: (v: T) => void; let reject!: (v: Error) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
afterEach(() => vi.useRealTimers())
describe('scoped reads invalidate protected state', () => {
  it('relation lookup cannot resurrect an old object, account, permission or disposed result', async () => {
    const state = reactive({ id: 1, allowed: true, account: 'A' })
    const first = deferred<string>(); const second = deferred<string>(); const last = deferred<string>()
    const load = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise).mockReturnValueOnce(last.promise)
    const scope = effectScope(); const value = scope.run(() => useScopedLookup(() => [state.id, state.allowed, state.account], load))!
    state.id = 2; second.resolve('B visible'); await flushPromises(); expect(value.value).toBe('B visible')
    first.resolve('A hidden'); await flushPromises(); expect(value.value).toBe('B visible')
    state.account = 'B'; expect(value.value).toBeNull(); state.allowed = false
    last.resolve('old account'); await flushPromises(); expect(value.value).toBeNull()
    expect(load).toHaveBeenCalledTimes(3)
    state.allowed = true; load.mockResolvedValue('visible'); scope.stop(); await flushPromises(); expect(value.value).toBeNull()
  })
  it.each([403, 404, 500])('failed optional lookup %s leaves no metadata', async code => {
    const scope = effectScope(); const load = vi.fn().mockRejectedValue(new Error(String(code)))
    const value = scope.run(() => useScopedLookup(() => [7, true, 'A'], load))!
    await flushPromises(); expect(value.value).toBeNull(); scope.stop()
  })
  it('no target permission means no lookup', async () => {
    const scope = effectScope(); const load = vi.fn(); scope.run(() => useScopedLookup(() => [1, false, 'A'], load))
    await flushPromises(); expect(load).not.toHaveBeenCalled(); scope.stop()
  })
  it('debounce, pagination, stale success/error/finally, close and account change are deterministic', async () => {
    vi.useFakeTimers()
    const identity = reactive({ allowed: true, session: 'A' })
    const old = deferred<any>(); const current = deferred<any>(); const page2 = deferred<any>()
    const fetch = vi.fn().mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise).mockReturnValueOnce(page2.promise)
    const scope = effectScope(); const search = scope.run(() => useScopedSearch(() => [identity.allowed, identity.session], fetch))!
    search.open(); expect(search.state.loading).toBe(true)
    search.search('a'); search.search('latest'); await vi.advanceTimersByTimeAsync(250)
    expect(fetch).toHaveBeenCalledTimes(2); expect(fetch).toHaveBeenLastCalledWith('latest', 1)
    old.reject(new Error('stale')); await flushPromises(); expect(search.state.error).toBe(false); expect(search.state.loading).toBe(true)
    current.resolve({ items: [{ id: 2, code: 'REQ-2', title: 'current', status: 'DONE' }], total: 40 }); await flushPromises()
    expect(search.state.items[0]?.id).toBe(2); search.paginate(2); expect(fetch).toHaveBeenLastCalledWith('latest', 2)
    identity.session = 'B'; expect(search.state.open).toBe(false); expect(search.state.items).toEqual([])
    page2.resolve({ items: [{ id: 3 }], total: 1 }); await flushPromises(); expect(search.state.items).toEqual([])
    identity.allowed = false; search.open(); expect(fetch).toHaveBeenCalledTimes(3)
    identity.allowed = true; fetch.mockRejectedValueOnce(new Error('offline')); search.open(); await flushPromises(); expect(search.state.error).toBe(true)
    fetch.mockResolvedValueOnce({ items: [], total: 0 }); await search.retry(); expect(search.state.error).toBe(false); expect(search.state.loading).toBe(false)
    search.search('pending'); search.close(); await vi.advanceTimersByTimeAsync(250); expect(fetch).toHaveBeenCalledTimes(5)
    const late = deferred<any>(); fetch.mockReturnValueOnce(late.promise); search.open(); scope.stop(); late.resolve({ items: [{ id: 99 }], total: 1 }); await flushPromises(); expect(search.state.items).toEqual([]); expect(search.state.loading).toBe(false)
  })
})
