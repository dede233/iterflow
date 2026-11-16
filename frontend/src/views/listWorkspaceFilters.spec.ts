import { reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ElementPlus from 'element-plus'

const mocks = vi.hoisted(() => ({ feedbacks: vi.fn(), versions: vi.fn(), push: vi.fn() }))
const route = reactive({ path: '/feedbacks', query: {} as Record<string, string> })
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ push: mocks.push }), onBeforeRouteLeave: vi.fn() }))
vi.mock('@/api/feedbacks', () => ({ listFeedbacks: mocks.feedbacks }))
vi.mock('@/api/versions', () => ({ listVersions: mocks.versions }))
vi.mock('@/api/systems', () => ({ listSystems: vi.fn().mockResolvedValue({ systems: [] }) }))
vi.mock('@/composables/useResponsive', () => ({ useResponsive: () => ({ isMobile: false }) }))
vi.mock('@/composables/usePermission', () => ({ usePermission: () => ({ can: () => false }) }))
import FeedbackListView from './feedback/FeedbackListView.vue'
import VersionListView from './version/VersionListView.vue'

const stubs = { BusinessSystemSelect: true, ListEntityFilterSelect: true, BatchActionsDialog: true, FeedbackCreateView: true, FeedbackDetailView: true, VersionCreateView: true, ReleaseVersionDrawer: true }
beforeEach(() => {
  vi.clearAllMocks()
  route.path = '/feedbacks'
  route.query = {}
  mocks.push.mockImplementation(async (target: { path: string; query: Record<string, string> }) => { route.path = target.path; route.query = target.query })
  mocks.feedbacks.mockResolvedValue({ total: 1, items: [{ id: 9, feedback_no: 'FB-0009', title: '反馈标题', status: 'NEW', feedback_type: 'NEW_FEATURE', urgency: 'NORMAL' }] })
  mocks.versions.mockResolvedValue({ total: 1, items: [{ id: 12, version_no: '2.2.31', name: '版本标题', status: 'READY' }] })
})

describe('workspace list filters', () => {
  it('removing an applied feedback condition preserves the URL snapshot instead of applying unsaved text', async () => {
    route.query = { keyword: '原条件', urgency: 'URGENT', page: '2' }
    const wrapper = mount(FeedbackListView, { global: { plugins: [ElementPlus], stubs } })
    await flushPromises()
    await wrapper.get('input[placeholder="编号 / 标题 / 描述"]').setValue('未提交文字')
    expect(wrapper.get('[aria-label="已应用筛选"]').text()).toContain('关键词：原条件')
    expect(wrapper.get('[aria-label="已应用筛选"]').text()).not.toContain('未提交文字')
    const chip = wrapper.findAll('.el-tag').find(item => item.text().includes('紧急度'))!
    await chip.get('.el-tag__close').trigger('click')
    await flushPromises()
    expect(route.query.keyword).toBe('原条件')
    expect(route.query.urgency).toBeUndefined()
    expect(mocks.feedbacks).toHaveBeenLastCalledWith(expect.objectContaining({ keyword: '原条件', urgency: undefined, page: 1 }))
    expect(wrapper.get('button.record-title').text()).toBe('反馈标题')
    wrapper.unmount()
  })

  it('clears both endpoints when the version date chip is removed and keeps other filters', async () => {
    route.path = '/versions'
    route.query = { status: 'READY', owner_id: '6', planned_release_from: '2026-11-01', planned_release_to: '2026-11-15', page: '3' }
    const wrapper = mount(VersionListView, { global: { plugins: [ElementPlus], stubs } })
    await flushPromises()
    const chip = wrapper.findAll('.el-tag').find(item => item.text().includes('计划上线'))!
    await chip.get('.el-tag__close').trigger('click')
    await flushPromises()
    expect(route.query.status).toBe('READY')
    expect(route.query.owner_id).toBe('6')
    expect(route.query.planned_release_from).toBeUndefined()
    expect(route.query.planned_release_to).toBeUndefined()
    expect(mocks.versions).toHaveBeenLastCalledWith(expect.objectContaining({ status: 'READY', owner_id: 6, planned_release_from: undefined, planned_release_to: undefined, page: 1 }))
    await wrapper.get('button.record-title').trigger('click')
    expect(wrapper.getComponent({ name: 'ReleaseVersionDrawer' }).props()).toMatchObject({ id: 12, modelValue: true })
    wrapper.unmount()
  })
})
