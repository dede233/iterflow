import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useUnsavedChanges } from './useUnsavedChanges'

const mocks = vi.hoisted(() => ({ confirm: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessageBox: { confirm: mocks.confirm } }))
const wrappers: ReturnType<typeof mount>[] = []
function setup() {
  const state = { dirty: true, busy: false, active: true }
  let guard!: ReturnType<typeof useUnsavedChanges>
  const wrapper = mount(defineComponent({ setup() {
    guard = useUnsavedChanges({ isDirty: () => state.dirty, isBusy: () => state.busy, active: () => state.active })
    return () => h('div')
  } }))
  wrappers.push(wrapper)
  return { guard, state, wrapper }
}
beforeEach(() => { mocks.confirm.mockReset() })
afterEach(() => { wrappers.splice(0).forEach(wrapper => wrapper.unmount()) })
describe('unsaved form protection', () => {
  it('allows clean and inactive forms without prompting, but blocks an active submission', async () => {
    const { guard, state } = setup()
    state.dirty = false
    expect(await guard.requestLeave()).toBe(true)
    state.busy = true
    expect(await guard.requestLeave()).toBe(false)
    state.active = false
    expect(await guard.requestLeave()).toBe(true)
    expect(mocks.confirm).not.toHaveBeenCalled()
  })
  it('preserves dirty state when continuing editing and shares one pending confirmation', async () => {
    const { guard, state } = setup()
    let reject!: (reason: unknown) => void
    mocks.confirm.mockImplementationOnce(() => new Promise((_resolve, fail) => { reject = fail }))
    const first = guard.requestLeave(), second = guard.requestLeave()
    expect(mocks.confirm).toHaveBeenCalledTimes(1)
    reject('cancel')
    expect(await first).toBe(false)
    expect(await second).toBe(false)
    expect(state.dirty).toBe(true)
    mocks.confirm.mockResolvedValue('confirm')
    expect(await guard.requestLeave()).toBe(true)
    expect(state.dirty).toBe(true)
  })
  it('does not leave if submission begins while the confirmation is open', async () => {
    const { guard, state } = setup()
    let resolve!: (value: string) => void
    mocks.confirm.mockImplementation(() => new Promise(done => { resolve = done }))
    const pending = guard.requestLeave()
    state.busy = true
    resolve('confirm')
    expect(await pending).toBe(false)
  })
  it('does not approve a stale confirmation after the owning form has unmounted', async () => {
    const { guard, wrapper } = setup()
    let resolve!: (value: string) => void
    mocks.confirm.mockImplementation(() => new Promise(done => { resolve = done }))
    const pending = guard.requestLeave()
    wrapper.unmount()
    resolve('confirm')
    expect(await pending).toBe(false)
  })
  it('protects reload only for active dirty/busy forms and removes its listener on disposal', () => {
    const { state, wrapper } = setup()
    const unload = () => { const event = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(event); return event.defaultPrevented }
    expect(unload()).toBe(true)
    state.dirty = false
    expect(unload()).toBe(false)
    state.busy = true
    expect(unload()).toBe(true)
    wrapper.unmount()
    expect(unload()).toBe(false)
  })
})
