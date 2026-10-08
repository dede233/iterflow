import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { expect, it } from 'vitest'
import { useDetailNavigation } from './useDetailNavigation'

async function navigation(path: string, defaultList: string) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }] })
  await router.push(path)
  let state!: ReturnType<typeof useDetailNavigation>
  const wrapper = mount(defineComponent({ setup() {
    state = useDetailNavigation(defaultList)
    return () => null
  } }), { global: { plugins: [router] } })
  return { state, router, wrapper }
}

it.each(['/feedbacks', '/requirements', '/versions'])('embedded %s navigation preserves only applied list fields', async path => {
  const { state, wrapper } = await navigation(`${path}?page=2&keyword=context&unknown=drop&return_to=https://evil.test`, path)
  expect(state.backTo.value).toBe(`${path}?page=2&keyword=context`)
  expect(state.related('/requirements/7')).toBe(`/requirements/7?return_to=${encodeURIComponent(state.backTo.value)}`)
  wrapper.unmount()
})

it('standalone details preserve safe return context and react to navigation', async () => {
  const target = '/feedbacks?page=2&status=ACCEPTED'
  const { state, router, wrapper } = await navigation(`/requirements/7?return_to=${encodeURIComponent(target)}`, '/requirements')
  expect(state.backTo.value).toBe(target)
  expect(state.related('/versions/3')).toBe(`/versions/3?return_to=${encodeURIComponent(target)}`)
  await router.push('/requirements/8')
  await flushPromises()
  expect(state.backTo.value).toBe('/requirements')
  wrapper.unmount()
})

it.each(['//evil.test', '/feedbacks?return_to=/versions', '/feedbacks?page=2&page=3'])('standalone details reject unsafe return target %s', async target => {
  const { state, wrapper } = await navigation(`/versions/7?return_to=${encodeURIComponent(target)}`, '/versions')
  expect(state.backTo.value).toBe('/versions')
  wrapper.unmount()
})
