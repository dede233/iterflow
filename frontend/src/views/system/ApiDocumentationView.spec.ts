/** @vitest-environment jsdom */
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import { getApiDocumentation } from '@/api/documentation'
import ApiDocumentationView from './ApiDocumentationView.vue'
import type { CurrentUser } from '@/types/auth'
import type { OpenApiDocument } from '@/utils/apiDocumentation'

vi.mock('@/api/documentation', () => ({ getApiDocumentation: vi.fn() }))
afterEach(() => vi.clearAllMocks())

it('does not reveal an in-flight schema after documentation eligibility is revoked', async () => {
  let resolve!: (document: OpenApiDocument) => void
  vi.mocked(getApiDocumentation).mockReturnValue(new Promise(done => { resolve = done }))
  const pinia = createPinia()
  const auth = useAuthStore(pinia)
  auth.user = { id: 1, can_view_api_docs: true } as CurrentUser
  const wrapper = mount(ApiDocumentationView, { global: {
    plugins: [pinia], directives: { loading: () => {} },
    stubs: { PageHeader: true, SectionCard: true, ErrorState: true, EmptyState: true, ApiSchemaView: true, ElButton: true },
  } })
  expect(getApiDocumentation).toHaveBeenCalledOnce()
  auth.user.can_view_api_docs = false
  await flushPromises()
  resolve({ info: { title: 'Private schema', version: '1.8.1' }, paths: { '/api/v1/private': { get: { summary: 'Private operation' } } } })
  await flushPromises()
  expect(wrapper.findComponent({ name: 'ErrorState' }).exists()).toBe(true)
  expect(wrapper.text()).not.toContain('Private operation')
  expect(wrapper.findComponent({ name: 'SectionCard' }).exists()).toBe(false)
  wrapper.unmount()
})
