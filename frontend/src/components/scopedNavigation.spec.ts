import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
const mocks = vi.hoisted(() => ({ get: vi.fn(), list: vi.fn() }))
vi.mock('@/api/requirements', () => ({ getRequirement: mocks.get, listRequirements: mocks.list }))
import ScopedRelationLink from './ScopedRelationLink.vue'
import ScopedObjectSelector from './ScopedObjectSelector.vue'
beforeEach(() => { vi.resetAllMocks(); setActivePinia(createPinia()) })
function session(permissions: string[], id = 1) { const auth = useAuthStore(); auth.user = { id, permission_codes: permissions } as any; auth.accessToken = `account-${id}`; return auth }
async function relation() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }] }); await router.push('/')
  return mount(ScopedRelationLink, { props: { kind: 'requirement', id: 7, returnTo: '/feedbacks?page=2', parentIdentity: 'FB-1' }, global: { plugins: [router] } })
}
it('permission is distinct from relation ID; no permission means no GET/link/metadata', async () => {
  session(['rd.feedback.view']); const wrapper = await relation(); await flushPromises()
  expect(wrapper.text()).toBe('#7'); expect(wrapper.find('a').exists()).toBe(false); expect(mocks.get).not.toHaveBeenCalled(); wrapper.unmount()
})
it.each([403, 404, 500])('target scope failure %s retains only parent ID', async status => {
  session(['rd.requirement.view']); mocks.get.mockRejectedValue({ response: { status } }); const wrapper = await relation(); await flushPromises()
  expect(wrapper.text()).toBe('#7'); expect(wrapper.find('a').exists()).toBe(false); wrapper.unmount()
})
it('scoped success links safely and permission/account switch removes old metadata immediately', async () => {
  const auth = session(['rd.requirement.view']); mocks.get.mockResolvedValue({ id: 7, requirement_no: 'REQ-7', title: '<script>private title</script>' })
  const wrapper = await relation(); await flushPromises()
  expect(wrapper.get('a').attributes('href')).toBe('/requirements/7?return_to=%2Ffeedbacks%3Fpage%3D2')
  expect(wrapper.find('script').exists()).toBe(false)
  auth.user = { id: 2, permission_codes: ['rd.feedback.view'] } as any; await flushPromises()
  expect(wrapper.text()).toBe('#7'); expect(wrapper.find('a').exists()).toBe(false); wrapper.unmount()
})
it('even allowed prop cannot bypass actual target permission; numeric ID fallback performs no directory query', async () => {
  session(['rd.version.edit']); const wrapper = mount(ScopedObjectSelector, { props: { kind: 'requirement', allowed: true, active: true }, global: { plugins: [ElementPlus] } })
  expect(wrapper.find('.el-input-number').exists()).toBe(true); expect(wrapper.findAll('button').some(x => x.text().includes('选择需求'))).toBe(false); expect(mocks.list).not.toHaveBeenCalled(); wrapper.unmount()
})
it('selector uses paginated scoped API, exposes minimal fields and clears results on close', async () => {
  session(['rd.requirement.view']); mocks.list.mockResolvedValue({ items: [{ id: 7, requirement_no: 'REQ-7', title: '可见需求', status: 'DONE', description: 'must not render', owner_id: 99, revision: 12 }], total: 1 })
  const wrapper = mount(ScopedObjectSelector, { props: { kind: 'requirement', allowed: true, active: true }, global: { plugins: [ElementPlus] }, attachTo: document.body })
  await wrapper.findAll('button').find(x => x.text() === '选择需求')!.trigger('click'); await flushPromises()
  expect(mocks.list).toHaveBeenCalledWith({ keyword: undefined, page: 1, page_size: 20 })
  const option = document.querySelector<HTMLButtonElement>('.selector-option')!; expect(option.textContent).toContain('已完成'); expect(document.body.textContent).not.toContain('must not render'); option.click(); await flushPromises()
  expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([7]); expect(wrapper.text()).toContain('REQ-7'); wrapper.unmount()
})
