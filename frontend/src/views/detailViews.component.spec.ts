import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Feedback, Requirement, VersionItem } from '@/types/domain'

const mocks = vi.hoisted(() => ({
  can: vi.fn<(permission: string | string[]) => boolean>(),
  routerPush: vi.fn(),
  getVersion: vi.fn(),
  listVersionRequirements: vi.fn(),
  listReleases: vi.fn(),
  getRequirement: vi.fn(),
  listRequirementFeedbacks: vi.fn(),
  editingHeartbeat: vi.fn(),
  startEditing: vi.fn(),
  endEditing: vi.fn(),
  getFeedback: vi.fn(),
  listFeedbackAttachments: vi.fn(),
  listFeedbackComments: vi.fn(),
  convertFeedback: vi.fn(),
  updateFeedback: vi.fn(),
  changeFeedbackStatus: vi.fn(),
  createFeedbackComment: vi.fn(),
  downloadFeedbackAttachment: vi.fn(),
  uploadFeedbackAttachment: vi.fn(),
  createRequirement: vi.fn(),
  createMessage: vi.fn(),
  warningMessage: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '7' } }),
  useRouter: () => ({ push: mocks.routerPush, replace: vi.fn(), back: vi.fn() }),
}))
vi.mock('@/composables/usePermission', () => ({ usePermission: () => ({ can: mocks.can }) }))
vi.mock('element-plus', () => ({
  ElMessage: { success: mocks.createMessage, warning: mocks.warningMessage },
  ElMessageBox: { confirm: vi.fn() },
}))
vi.mock('@/api/versions', () => ({
  addVersionRequirement: vi.fn(),
  changeVersionStatus: vi.fn(),
  checkVersionPublish: vi.fn(),
  getVersion: mocks.getVersion,
  listVersionRequirements: mocks.listVersionRequirements,
  moveVersionRequirement: vi.fn(),
  publishVersion: vi.fn(),
  removeVersionRequirement: vi.fn(),
  updateVersion: vi.fn(),
}))
vi.mock('@/api/releases', () => ({ listReleases: mocks.listReleases }))
vi.mock('@/api/requirements', () => ({
  changeRequirementStatus: vi.fn(),
  createRequirement: mocks.createRequirement,
  getRequirement: mocks.getRequirement,
  listRequirementFeedbacks: mocks.listRequirementFeedbacks,
  updateRequirement: vi.fn(),
}))
vi.mock('@/api/editing', () => ({
  editingHeartbeat: mocks.editingHeartbeat,
  endEditing: mocks.endEditing,
  startEditing: mocks.startEditing,
}))
vi.mock('@/api/feedbacks', () => ({
  changeFeedbackStatus: mocks.changeFeedbackStatus,
  convertFeedback: mocks.convertFeedback,
  createFeedbackComment: mocks.createFeedbackComment,
  downloadFeedbackAttachment: mocks.downloadFeedbackAttachment,
  getFeedback: mocks.getFeedback,
  listFeedbackAttachments: mocks.listFeedbackAttachments,
  listFeedbackComments: mocks.listFeedbackComments,
  updateFeedback: mocks.updateFeedback,
  uploadFeedbackAttachment: mocks.uploadFeedbackAttachment,
}))

import VersionDetailView from '@/views/version/VersionDetailView.vue'
import RequirementDetailView from '@/views/requirement/RequirementDetailView.vue'
import FeedbackDetailView from '@/views/feedback/FeedbackDetailView.vue'

const version: VersionItem = {
  id: 7,
  version_no: 'V1.5.0',
  name: '1.5.0',
  status: 'PLANNING',
  owner_id: null,
  planned_release_date: null,
  released_at: null,
  description: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  updated_by: null,
  revision: 1,
}

const requirement: Requirement = {
  id: 9,
  requirement_no: 'REQ-0009',
  title: '需求标题',
  requirement_type: 'FEATURE',
  source: 'DIRECT',
  priority: 'P2',
  status: 'CONFIRMED',
  system_id: null,
  module_id: null,
  owner_id: null,
  current_version_id: null,
  description: '需求描述',
  acceptance_criteria: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  updated_by: null,
  revision: 1,
}

const feedback: Feedback = {
  id: 7,
  feedback_no: 'FB-0007',
  title: '反馈标题',
  feedback_type: 'OTHER',
  urgency: 'NORMAL',
  status: 'ACCEPTED',
  system_id: null,
  module_id: null,
  submitter_id: 4,
  description: '反馈描述',
  expected_result: null,
  actual_result: null,
  reproduce_steps: null,
  main_requirement_id: null,
  duplicate_of_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  updated_by: null,
  revision: 1,
}

const elementStub = { template: '<div><slot /><slot name="footer" /></div>' }
const stubs = {
  'el-alert': elementStub,
  'el-button': {
    template: '<button v-bind="$attrs" @click="$emit(\'click\', $event)"><slot /></button>',
    emits: ['click'],
  },
  'el-dialog': {
    props: { modelValue: Boolean },
    template: '<div v-if="modelValue" class="dialog"><slot /><slot name="footer" /></div>',
  },
  'el-card': { template: '<div class="card"><slot /></div>' },
  'el-checkbox': elementStub,
  'el-checkbox-group': elementStub,
  'el-col': elementStub,
  'el-collapse': elementStub,
  'el-collapse-item': elementStub,
  'el-date-picker': elementStub,
  'el-descriptions': elementStub,
  'el-descriptions-item': elementStub,
  'el-drawer': elementStub,
  'el-empty': {
    props: { description: String },
    template: '<div class="empty">{{ description }}</div>',
  },
  'el-form': elementStub,
  'el-form-item': elementStub,
  'el-input': elementStub,
  'el-input-number': elementStub,
  'el-link': elementStub,
  'el-option': elementStub,
  'el-pagination': elementStub,
  'el-progress': elementStub,
  'el-radio': elementStub,
  'el-radio-group': elementStub,
  'el-result': elementStub,
  'el-row': elementStub,
  'el-select': elementStub,
  'el-skeleton': elementStub,
  'el-switch': elementStub,
  'el-table': elementStub,
  'el-table-column': elementStub,
  'el-tag': elementStub,
  'el-upload': elementStub,
  StatusTag: { props: ['status', 'label', 'type'], template: '<span>{{ label }}</span>' },
}

function permissionSet(...permissions: string[]): void {
  mocks.can.mockImplementation((permission) => {
    const requested = Array.isArray(permission) ? permission : [permission]
    return requested.some((code) => permissions.includes(code))
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  permissionSet()
  mocks.getVersion.mockResolvedValue(version)
  mocks.listVersionRequirements.mockResolvedValue({
    version_id: version.id,
    stats: { total: 0, by_status: {}, completed: 0, completion_rate: 0 },
    items: [],
  })
  mocks.listReleases.mockResolvedValue({ items: [], page: 1, page_size: 20, total: 0 })
  mocks.getRequirement.mockResolvedValue(requirement)
  mocks.listRequirementFeedbacks.mockResolvedValue([])
  mocks.startEditing.mockResolvedValue({})
  mocks.getFeedback.mockResolvedValue(feedback)
  mocks.listFeedbackAttachments.mockResolvedValue([])
  mocks.listFeedbackComments.mockResolvedValue([])
  mocks.convertFeedback.mockResolvedValue(requirement)
})

describe('detail views enforce permission-aware loading in mounted components', () => {
  it('keeps Version visible without fetching or rendering unauthorized child sections', async () => {
    permissionSet('rd.version.view')
    const wrapper = mount(VersionDetailView, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    expect(mocks.getVersion).toHaveBeenCalledOnce()
    expect(mocks.listVersionRequirements).not.toHaveBeenCalled()
    expect(mocks.listReleases).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('1.5.0')
    expect(wrapper.text()).not.toContain('可见需求清单')
    expect(wrapper.text()).not.toContain('发布历史')
  })

  it('loads each Version child section only with its domain permission', async () => {
    permissionSet('rd.version.view', 'rd.requirement.view')
    const wrapper = mount(VersionDetailView, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()
    expect(mocks.listVersionRequirements).toHaveBeenCalledOnce()
    expect(mocks.listReleases).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('可见需求清单')
    expect(wrapper.text()).not.toContain('发布历史')
    wrapper.unmount()

    vi.clearAllMocks()
    permissionSet('rd.version.view', 'rd.release.view')
    const releasesOnly = mount(VersionDetailView, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()
    expect(mocks.listVersionRequirements).not.toHaveBeenCalled()
    expect(mocks.listReleases).toHaveBeenCalledOnce()
    expect(releasesOnly.text()).not.toContain('可见需求清单')
    expect(releasesOnly.text()).toContain('发布历史')
  })

  it('does not fetch linked Feedback or create editing presence for a read-only Requirement viewer', async () => {
    permissionSet('rd.requirement.view')
    const wrapper = mount(RequirementDetailView, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    expect(mocks.getRequirement).toHaveBeenCalledOnce()
    expect(mocks.listRequirementFeedbacks).not.toHaveBeenCalled()
    expect(mocks.startEditing).not.toHaveBeenCalled()
    expect(mocks.editingHeartbeat).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('需求标题')
    expect(wrapper.text()).not.toContain('来源反馈')
    wrapper.unmount()
    expect(mocks.endEditing).not.toHaveBeenCalled()
  })

  it('shows linked Feedback only when the mounted Requirement viewer has Feedback read permission', async () => {
    permissionSet('rd.requirement.view', 'rd.feedback.view')
    const wrapper = mount(RequirementDetailView, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    expect(mocks.listRequirementFeedbacks).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('来源反馈')
    expect(wrapper.text()).toContain('暂无可见来源反馈')
  })

  it('allows CREATE_NEW without LINK_EXISTING and reloads Feedback without navigation', async () => {
    permissionSet('rd.feedback.view', 'rd.feedback.convert')
    const wrapper = mount(FeedbackDetailView, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    expect(wrapper.text()).toContain('反馈标题')
    const convertButton = wrapper.findAll('button').find((button) => button.text() === '转需求')
    expect(convertButton).toBeDefined()
    await convertButton!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('新建需求')
    expect(wrapper.text()).not.toContain('关联已有需求')

    const confirmButton = wrapper.findAll('button').find((button) => button.text() === '确定')
    expect(confirmButton).toBeDefined()
    await confirmButton!.trigger('click')
    await flushPromises()

    expect(mocks.convertFeedback).toHaveBeenCalledOnce()
    expect(mocks.routerPush).not.toHaveBeenCalled()
    expect(mocks.getFeedback).toHaveBeenCalledTimes(2)
  })

  it('offers LINK_EXISTING when the mounted converter can read Requirements', async () => {
    permissionSet('rd.feedback.view', 'rd.feedback.convert', 'rd.requirement.view')
    const wrapper = mount(FeedbackDetailView, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()
    const convertButton = wrapper.findAll('button').find((button) => button.text() === '转需求')
    await convertButton!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('关联已有需求')
  })
})
