import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
const mocks = vi.hoisted(() => ({ list: vi.fn(), post: vi.fn() }))
vi.mock('@/api/requirements', () => ({ listRequirements: mocks.list }))
vi.mock('@/api/client', () => ({ api: { post: mocks.post } }))
import BulkRequirementPicker from './BulkRequirementPicker.vue'
const browserCrypto = globalThis.crypto
afterEach(() => vi.unstubAllGlobals())
beforeEach(() => {
  vi.resetAllMocks(); setActivePinia(createPinia())
  useAuthStore().user = { id: 1, permission_codes: ['rd.requirement.view'] } as any
  mocks.list.mockImplementation(({ page }) => Promise.resolve({ total: 40, items: [{ id: page, revision: page + 2, title: `需求 ${page}`, requirement_no: `REQ-${page}`, status: 'DRAFT', current_version_id: null }] }))
})
it.each([true, false])('keeps revisions and sends a valid UUID with randomUUID available=%s', async available => {
  vi.stubGlobal('crypto', {
    getRandomValues: browserCrypto.getRandomValues.bind(browserCrypto),
    randomUUID: available ? browserCrypto.randomUUID.bind(browserCrypto) : undefined,
  })
  mocks.post.mockRejectedValue({ response: { status: 409, data: { data: { items: [{ requirement_id: 1, reason: '已修改' }] } } } })
  const wrapper = mount(BulkRequirementPicker, { props: { versionId: 7, revision: 9 }, global: { directives: { loading: () => {} }, stubs: {
    'el-form': { template: '<form><slot/></form>' }, 'el-form-item': { template: '<div><slot/></div>' },
    'el-select': true, 'el-option': true, 'el-input': true,
    'el-button': { template: '<button><slot/></button>' },
    'el-checkbox': { name: 'Choice', props: ['modelValue'], template: '<button @click="$emit(\'change\', !modelValue)"><slot/></button>' },
    'el-pagination': { name: 'Pager', template: '<button @click="$emit(\'current-change\', 2)">next page</button>' },
  } } })
  await flushPromises()
  await wrapper.findComponent({ name: 'Choice' }).trigger('click')
  await wrapper.findComponent({ name: 'Pager' }).trigger('click'); await flushPromises()
  await wrapper.findComponent({ name: 'Choice' }).trigger('click')
  await wrapper.findAll('button').find(b => b.text() === '添加 2 条需求')!.trigger('click'); await flushPromises()
  expect(mocks.post).toHaveBeenCalledWith('/versions/7/requirements/batch', { version_revision: 9, request_id: expect.stringMatching(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/), items: [{ requirement_id: 1, revision: 3 }, { requirement_id: 2, revision: 4 }] })
  expect(wrapper.get('[role="alert"]').text()).toContain('已修改')
  expect(wrapper.text()).toContain('已选 2 / 50')
  expect(mocks.post).toHaveBeenCalledTimes(1)
  wrapper.unmount()
})
