import { defineComponent, reactive } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import { useListQuery } from './useListQuery'
it('restores URL, keeps draft out of pagination, persists apply/reset and browser back', async () => {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/requirements', component: { template: '<div />' } }] })
  await router.push('/requirements?page=2&keyword=applied&priority=P1&owner_id=7&garbage=x')
  const draft = reactive<Record<string, unknown>>({})
  const snapshots: Record<string, string>[] = []; const invalidate = vi.fn()
  let state!: ReturnType<typeof useListQuery>
  const wrapper = mount(defineComponent({ setup() {
    state = useListQuery({ path: '/requirements', readDraft: () => draft, restore: q => { for (const key of Object.keys(draft)) delete draft[key]; Object.assign(draft, q) }, load: async () => { snapshots.push(state.applied()) }, invalidate })
    return () => null
  } }), { global: { plugins: [router] } })
  await flushPromises(); expect(snapshots.at(-1)).toEqual({ page: '2', keyword: 'applied', priority: 'P1', owner_id: '7' })
  draft.keyword = 'unapplied'; await state.paginate(3); await flushPromises()
  expect(snapshots.at(-1)?.keyword).toBe('applied'); expect(router.currentRoute.value.query.page).toBe('3')
  draft.keyword = 'next'; await state.apply(); await flushPromises()
  expect(snapshots.at(-1)).toEqual({ keyword: 'next', priority: 'P1', owner_id: '7' })
  expect(state.detail('/requirements/9')).toBe('/requirements/9?return_to=%2Frequirements%3Fkeyword%3Dnext%26priority%3DP1%26owner_id%3D7')
  await state.reset(); await flushPromises(); expect(router.currentRoute.value.query).toEqual({}); expect(snapshots.at(-1)).toEqual({})
  router.back(); await flushPromises(); expect(draft.keyword).toBe('next'); expect(snapshots.at(-1)?.keyword).toBe('next')
  const count = snapshots.length; wrapper.unmount(); await router.push('/requirements?keyword=after'); await flushPromises(); expect(snapshots).toHaveLength(count); expect(invalidate).toHaveBeenCalled()
})

it('reset removes invalid/unknown query fields even when the applied snapshot is already empty', async () => {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/versions', component: { template: '<div />' } }] })
  await router.push('/versions?page=0&unknown=bad&planned_release_from=2026-10-01')
  let state!: ReturnType<typeof useListQuery>
  const wrapper = mount(defineComponent({ setup() { state = useListQuery({ path: '/versions', readDraft: () => ({}), restore: () => {}, load: async () => {}, invalidate: () => {} }); return () => null } }), { global: { plugins: [router] } })
  expect(state.applied()).toEqual({}); await state.reset(); await flushPromises(); expect(router.currentRoute.value.fullPath).toBe('/versions'); wrapper.unmount()
})
