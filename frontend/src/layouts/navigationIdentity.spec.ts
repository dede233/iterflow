import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'
import { createMemoryHistory, createRouter, useRoute } from 'vue-router'
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
vi.mock('@/composables/useNotificationFreshness', () => ({ useNotificationFreshness: () => {} }))
import AppLayout from './AppLayout.vue'
it('route identity and account/scope changes remount details but query changes do not cache or remount', async () => {
  const pinia = createPinia(); setActivePinia(pinia); const auth = useAuthStore()
  auth.user = { id: 1, data_scope: 'ALL', permission_codes: ['rd.requirement.view'] } as any
  let mounts = 0
  const child = defineComponent({ setup() { mounts++; const id = useRoute().params.id; const user = auth.user!.id; return () => h('p', { class: 'identity' }, `${id}:${user}`) } })
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: AppLayout, children: [{ path: 'requirements/:id', component: child }] }] })
  await router.push('/requirements/1')
  const wrapper = mount(defineComponent({ template: '<router-view />' }), { global: { plugins: [pinia, router], stubs: { MobileBottomNav: true, AppIcon: true } } }); await flushPromises()
  expect(wrapper.get('.identity').text()).toBe('1:1')
  await router.push('/requirements/2'); await flushPromises(); expect(wrapper.get('.identity').text()).toBe('2:1'); expect(mounts).toBe(2)
  await router.push('/requirements/2?return_to=%2Frequirements'); await flushPromises(); expect(mounts).toBe(2)
  auth.user = { id: 2, data_scope: 'SELF', permission_codes: ['rd.requirement.view'] } as any; await flushPromises(); expect(wrapper.get('.identity').text()).toBe('2:2'); expect(mounts).toBe(3)
  auth.user.data_scope = 'ALL'; await flushPromises(); expect(mounts).toBe(4)
  auth.reset(); await flushPromises(); expect(wrapper.find('.identity').exists()).toBe(false)
  wrapper.unmount()
})
