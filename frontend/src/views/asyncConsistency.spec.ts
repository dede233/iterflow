import { reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElTable, ElMessage } from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'
const mocks = vi.hoisted(() => ({ feedbacks: vi.fn(), audits: vi.fn(), detail: vi.fn() }))
vi.mock('@/api/feedbacks', () => ({ listFeedbacks: mocks.feedbacks, createFeedback: vi.fn() }))
vi.mock('@/api/audits', () => ({ listAudits: mocks.audits, getAudit: mocks.detail }))
vi.mock('@/api/systems', () => ({ listSystems: vi.fn() }))
vi.mock('@/composables/usePermission', () => ({ usePermission: () => ({ can: () => false }) }))
vi.mock('@/composables/useResponsive', () => ({ useResponsive: () => ({ isMobile: false }) }))
const route = reactive({ query: {} as Record<string, string> })
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ push: async (target: { query?: Record<string, string> }) => { route.query = target.query ?? {} } }) }))
import FeedbackList from './feedback/FeedbackListView.vue'
import AuditCenter from './audit/AuditCenterView.vue'
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const audit = (id: number) => ({ id, entity_type: 'FEEDBACK', entity_id: id, action: 'CREATE', created_at: '2026-10-01T00:00:00Z', operator: null, before: null, after: { marker: `detail-${id}` } })
const page = (id: number) => ({ items: [{ ...audit(id), title: `result-${id}`, feedback_no: `FB-${id}`, feedback_type: 'OTHER', urgency: 'NORMAL', status: 'NEW' }], total: id, page: 1, size: 20, page_size: 20 })
function view(component: typeof FeedbackList | typeof AuditCenter) {
  const loading = (el: HTMLElement, binding: { value: boolean }) => el.setAttribute('data-loading', String(binding.value))
  return mount(component, { global: {
    plugins: [ElementPlus], directives: { loading: { mounted: loading, updated: loading } },
    stubs: {
      FeedbackCreateView: true,
      ElDrawer: { name: 'ElDrawer', props: ['modelValue', 'title'], emits: ['update:modelValue'], template: '<div v-if="modelValue" class="test-drawer"><button @click="$emit(\'update:modelValue\', false)">关闭</button><slot /><slot name="footer" /></div>' },
    },
  } })
}
beforeEach(() => { vi.resetAllMocks(); route.query = {}; mocks.feedbacks.mockResolvedValue(page(1)); mocks.audits.mockResolvedValue(page(1)); mocks.detail.mockImplementation(async (id: number) => audit(id)) })
for (const config of [{ name: 'Feedback list', component: FeedbackList, api: mocks.feedbacks }, { name: 'Audit list', component: AuditCenter, api: mocks.audits }]) {
 describe(config.name, () => {
  it('ignores a stale success after the latest query succeeds', async () => {
    const old = deferred<ReturnType<typeof page>>()
    config.api.mockReturnValueOnce(old.promise).mockResolvedValueOnce(page(2))
    const wrapper = view(config.component); await flushPromises()
    await (config.name === 'Audit list' ? wrapper.get('form.filters').trigger('submit') : wrapper.findAll('button').find(b => b.text() === '查询')!.trigger('click')); await flushPromises()
    expect(wrapper.findComponent(ElTable).props('data')[0].id).toBe(2)
    old.resolve(page(1)); await flushPromises()
    expect(wrapper.findComponent(ElTable).props('data')[0].id).toBe(2)
    expect(wrapper.text()).toContain('共 2'); wrapper.unmount()
  })
  it('does not let a stale failure clear latest loading or show an error', async () => {
    const old = deferred<ReturnType<typeof page>>(); const latest = deferred<ReturnType<typeof page>>()
    config.api.mockReturnValueOnce(old.promise).mockReturnValueOnce(latest.promise)
    const wrapper = view(config.component); await flushPromises()
    await (config.name === 'Audit list' ? wrapper.get('form.filters').trigger('submit') : wrapper.findAll('button').find(b => b.text() === '查询')!.trigger('click'))
    old.reject(new Error('stale failure')); await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.findComponent(ElTable).attributes('data-loading')).toBe('true')
    latest.resolve(page(2)); await flushPromises()
    expect(wrapper.findComponent(ElTable).attributes('data-loading')).toBe('false'); wrapper.unmount()
  })
 })
}
describe('Audit detail', () => {
 it('preserves newer detail when the old request completes last', async () => {
    const old = deferred<ReturnType<typeof audit>>()
    mocks.detail.mockReturnValueOnce(old.promise).mockResolvedValueOnce(audit(2))
    const wrapper = view(AuditCenter); await flushPromises()
    wrapper.findComponent(ElTable).vm.$emit('row-click', audit(1)); await flushPromises()
    wrapper.findComponent(ElTable).vm.$emit('row-click', audit(2)); await flushPromises()
    expect(wrapper.get('.drawer-content').text()).toContain('detail-2')
    old.resolve(audit(1)); await flushPromises()
    expect(wrapper.get('.drawer-content').text()).toContain('detail-2'); wrapper.unmount()
 })
 it('does not close a newer detail or clear its loading after an old failure', async () => {
    const old = deferred<ReturnType<typeof audit>>(); const latest = deferred<ReturnType<typeof audit>>()
    mocks.detail.mockReturnValueOnce(old.promise).mockReturnValueOnce(latest.promise)
    const error = vi.spyOn(ElMessage, 'error'); const wrapper = view(AuditCenter); await flushPromises()
    wrapper.findComponent(ElTable).vm.$emit('row-click', audit(1)); await flushPromises()
    wrapper.findComponent(ElTable).vm.$emit('row-click', audit(2)); await flushPromises()
    old.reject(new Error('stale')); await flushPromises()
    expect(wrapper.get('.drawer-content').attributes('data-loading')).toBe('true')
    expect(error).not.toHaveBeenCalled()
    latest.resolve(audit(2)); await flushPromises()
    expect(wrapper.get('.drawer-content').text()).toContain('detail-2'); wrapper.unmount(); error.mockRestore(); ElMessage.closeAll()
 })
 it('invalidates a detail on close and ignores its late failure', async () => {
    const old = deferred<ReturnType<typeof audit>>(); mocks.detail.mockReturnValueOnce(old.promise)
    const error = vi.spyOn(ElMessage, 'error'); const wrapper = view(AuditCenter); await flushPromises()
    wrapper.findComponent(ElTable).vm.$emit('row-click', audit(1)); await flushPromises()
    await wrapper.get('.test-drawer button').trigger('click')
    old.reject(new Error('after close')); await flushPromises()
    expect(error).not.toHaveBeenCalled(); expect(wrapper.find('.drawer-content').exists()).toBe(false)
    wrapper.unmount(); error.mockRestore(); ElMessage.closeAll()
 })
})
