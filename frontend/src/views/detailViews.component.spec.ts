import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Feedback, Requirement, VersionItem } from '@/types/domain'

const mocks = vi.hoisted(() => ({
  can: vi.fn<(permission: string | string[]) => boolean>(),
  routerPush: vi.fn(),
  getVersion: vi.fn(),
  checkPublish: vi.fn(),
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
  updateRequirement: vi.fn(),
  updateVersion: vi.fn(),
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
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ hasPermission: mocks.can, user: { id: 1 }, accessToken: 'test', permissionCodes: [] }) }))
vi.mock('@/composables/usePermission', () => ({ usePermission: () => ({ can: mocks.can }) }))
vi.mock('element-plus', () => ({
  ElMessage: { success: mocks.createMessage, warning: mocks.warningMessage },
  ElMessageBox: { confirm: vi.fn() },
}))
vi.mock('@/api/versions', () => ({
  addVersionRequirement: vi.fn(),
  changeVersionStatus: vi.fn(),
  checkVersionPublish: mocks.checkPublish,
  getVersion: mocks.getVersion,
  listVersionRequirements: mocks.listVersionRequirements,
  moveVersionRequirement: vi.fn(),
  publishVersion: vi.fn(),
  removeVersionRequirement: vi.fn(),
  updateVersion: mocks.updateVersion,
}))
vi.mock('@/api/releases', () => ({ listReleases: mocks.listReleases }))
vi.mock('@/api/requirements', () => ({
  changeRequirementStatus: vi.fn(),
  createRequirement: mocks.createRequirement,
  getRequirement: mocks.getRequirement,
  listRequirementFeedbacks: mocks.listRequirementFeedbacks,
  updateRequirement: mocks.updateRequirement,
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
  'el-alert': { template: '<div class="alert"><slot name="title" /><slot /></div>' },
  'el-button': {
    template: '<button v-bind="$attrs" @click="$emit(\'click\', $event)"><slot /></button>',
    emits: ['click'],
  },
  'el-dialog': {
    name: 'ElDialog',
    props: { modelValue: Boolean },
    emits: ['update:modelValue'],
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
  'el-input': {
    name: 'ElInput',
    props: ['modelValue', 'type'],
    emits: ['update:modelValue'],
    template: '<textarea v-if="type === \'textarea\'" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" /><input v-else :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
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
  'el-table-column': { template: '<div />' },
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
  mocks.startEditing.mockResolvedValue({ existing_editor: null })
  mocks.endEditing.mockResolvedValue({ ok: true })
  mocks.editingHeartbeat.mockResolvedValue({ ok: true, existing_editor: null })
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
    expect(wrapper.text()).not.toContain('需求清单')
    expect(wrapper.text()).not.toContain('发布历史')
  })

  it('loads each Version child section only with its domain permission', async () => {
    permissionSet('rd.version.view', 'rd.requirement.view')
    const wrapper = mount(VersionDetailView, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()
    expect(mocks.listVersionRequirements).toHaveBeenCalledOnce()
    expect(mocks.listReleases).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('需求清单')
    expect(wrapper.text()).not.toContain('发布历史')
    wrapper.unmount()

    vi.clearAllMocks()
    permissionSet('rd.version.view', 'rd.release.view')
    const releasesOnly = mount(VersionDetailView, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()
    expect(mocks.listVersionRequirements).not.toHaveBeenCalled()
    expect(mocks.listReleases).toHaveBeenCalledOnce()
    expect(releasesOnly.text()).not.toContain('需求清单')
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

  it('does not start Requirement presence on detail mount, even with edit or status permission', async () => {
    permissionSet('rd.requirement.view', 'rd.requirement.edit', 'rd.requirement.status')
    const wrapper = mount(RequirementDetailView, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()
    expect(mocks.startEditing).not.toHaveBeenCalled()
    wrapper.unmount()
    expect(mocks.endEditing).not.toHaveBeenCalled()
  })

  it.each([
    { name: 'Feedback', component: FeedbackDetailView, permission: 'rd.feedback.edit', entity: 'FEEDBACK' },
    { name: 'Requirement', component: RequirementDetailView, permission: 'rd.requirement.edit', entity: 'REQUIREMENT' },
    { name: 'Version', component: VersionDetailView, permission: 'rd.version.edit', entity: 'VERSION' },
  ])('$name begins presence on Edit and ends it when the dialog closes', async ({ component, permission, entity }) => {
    permissionSet(permission)
    const wrapper = mount(component, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()
    expect(mocks.startEditing).not.toHaveBeenCalled()

    const editButton = wrapper.findAll('button').find((button) => button.text() === '编辑')
    expect(editButton).toBeDefined()
    await editButton!.trigger('click')
    await flushPromises()
    expect(mocks.startEditing).toHaveBeenCalledExactlyOnceWith(entity, 7)

    const cancelButton = wrapper.findAll('button').find((button) => button.text() === '取消')
    expect(cancelButton).toBeDefined()
    await cancelButton!.trigger('click')
    await flushPromises()
    expect(mocks.endEditing).toHaveBeenCalledExactlyOnceWith(entity, 7)
    wrapper.unmount()
    expect(mocks.endEditing).toHaveBeenCalledTimes(1)
  })

  it.each([
    { component: FeedbackDetailView, permission: 'rd.feedback.edit', update: mocks.updateFeedback },
    { component: RequirementDetailView, permission: 'rd.requirement.edit', update: mocks.updateRequirement },
    { component: VersionDetailView, permission: 'rd.version.edit', update: mocks.updateVersion },
  ])('keeps the field editor and presence open when saving fails', async ({ component, permission, update }) => {
    permissionSet(permission)
    update.mockRejectedValueOnce(new Error('save failed'))
    const wrapper = mount(component, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === '编辑')!.trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === '保存')!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.dialog').exists()).toBe(true)
    expect(wrapper.emitted('updated')).toBeUndefined()
    expect(mocks.endEditing).not.toHaveBeenCalled()
    wrapper.unmount()
    await flushPromises()
    expect(mocks.endEditing).toHaveBeenCalledOnce()
  })

  it.each([
    { name: 'Feedback', component: FeedbackDetailView, permission: 'rd.feedback.edit', update: mocks.updateFeedback, get: mocks.getFeedback, initial: feedback, field: '反馈标题', server: '服务器反馈' },
    { name: 'Requirement', component: RequirementDetailView, permission: 'rd.requirement.edit', update: mocks.updateRequirement, get: mocks.getRequirement, initial: requirement, field: '需求标题', server: '服务器需求' },
    { name: 'Version', component: VersionDetailView, permission: 'rd.version.edit', update: mocks.updateVersion, get: mocks.getVersion, initial: version, field: '1.5.0', server: '服务器版本' },
  ])('$name preserves local input and presence through revision conflict until explicit reload', async ({ name, component, permission, update, get, initial, field, server }) => {
    permissionSet(permission)
    const latest = { ...initial, ...(name === 'Version' ? { name: server } : { title: server }), revision: 2, updated_by: 8, updated_at: '2026-09-29T01:00:00Z' }
    get.mockResolvedValueOnce(initial).mockResolvedValue(latest)
    const stale = { response: { status: 409, data: { code: 40910, message: '已修改', data: { current_revision: 2, current_updated_at: latest.updated_at, current_updated_by: 8 } } } }
    update.mockRejectedValue(stale)
    const wrapper = mount(component, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === '编辑')!.trigger('click')
    await flushPromises()
    const input = wrapper.findAllComponents({ name: 'ElInput' }).find((entry) => entry.props('modelValue') === field)
    expect(input).toBeDefined()
    input!.vm.$emit('update:modelValue', '我的本地输入')
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === '保存')!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('你的输入仍保留在原表单中')
    expect(wrapper.text()).toContain(server)
    expect(wrapper.text()).toContain('用户 #8')
    expect(input!.props('modelValue')).toBe('我的本地输入')
    expect(mocks.endEditing).not.toHaveBeenCalled()
    expect(wrapper.findAll('button').find((button) => button.text() === '保存')?.attributes('disabled')).toBeUndefined()
    await wrapper.findAll('button').find((button) => button.text() === '关闭并人工处理')!.trigger('click')
    await flushPromises()
    expect(input!.props('modelValue')).toBe('我的本地输入')
    await wrapper.findAll('button').find((button) => button.text() === '保存')!.trigger('click')
    await flushPromises()
    expect(update).toHaveBeenLastCalledWith(initial.id, expect.objectContaining({ revision: 1 }))
    expect(wrapper.emitted('updated')).toBeUndefined()
    await wrapper.findAll('button').find((button) => button.text() === '重新加载服务器版本')!.trigger('click')
    await flushPromises()
    expect(input!.props('modelValue')).toBe(server)
    expect(wrapper.text()).not.toContain('你的输入仍保留在原表单中')
    expect(mocks.endEditing).not.toHaveBeenCalled()
    update.mockResolvedValueOnce(latest)
    await wrapper.findAll('button').find((button) => button.text() === '保存')!.trigger('click')
    await flushPromises()
    expect(update).toHaveBeenLastCalledWith(initial.id, expect.objectContaining({ revision: 2 }))
    expect(wrapper.emitted('updated')).toEqual([[]])
    expect(mocks.endEditing).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('ends Requirement presence when the dialog closes through model update', async () => {
    permissionSet('rd.requirement.edit')
    const wrapper = mount(RequirementDetailView, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === '编辑')!.trigger('click')
    await flushPromises()
    const editDialog = wrapper.findAllComponents({ name: 'ElDialog' }).find((dialog) => dialog.props('modelValue'))
    expect(editDialog).toBeDefined()
    editDialog!.vm.$emit('update:modelValue', false)
    await flushPromises()
    expect(mocks.endEditing).toHaveBeenCalledOnce()
  })

  it.each([
    { component: FeedbackDetailView, permission: 'rd.feedback.edit' },
    { component: RequirementDetailView, permission: 'rd.requirement.edit' },
    { component: VersionDetailView, permission: 'rd.version.edit' },
  ])('warns about another editor while keeping Save enabled', async ({ component, permission }) => {
    permissionSet(permission)
    mocks.startEditing.mockResolvedValueOnce({
      existing_editor: { user_id: 18, display_name: '测试用户B', active_at: '2026-09-29T00:00:00Z' },
    })
    const wrapper = mount(component, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === '编辑')!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.alert').text()).toContain('测试用户B 正在编辑')
    expect(wrapper.find('.alert').text()).toContain('仍可继续编辑')
    const saveButton = wrapper.findAll('button').find((button) => button.text() === '保存')
    expect(saveButton?.attributes('disabled')).toBeUndefined()
    wrapper.unmount()
    await flushPromises()
  })

  it.each([
    { component: FeedbackDetailView, permission: 'rd.feedback.view' },
    { component: RequirementDetailView, permission: 'rd.requirement.status' },
    { component: VersionDetailView, permission: 'rd.version.status' },
  ])('does not offer field editing or presence without its edit permission', async ({ component, permission }) => {
    permissionSet(permission)
    const wrapper = mount(component, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()
    expect(wrapper.findAll('button').some((button) => button.text() === '编辑')).toBe(false)
    expect(mocks.startEditing).not.toHaveBeenCalled()
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


it('publish check close/reopen invalidates old success and finally; server check remains authoritative', async () => {
  permissionSet('rd.version.view', 'rd.version.publish')
  mocks.getVersion.mockResolvedValue({ ...version, status: 'READY' })
  let oldFinish!: (value: unknown) => void
  let currentFinish!: (value: unknown) => void
  mocks.checkPublish.mockImplementationOnce(() => new Promise(resolve => { oldFinish = resolve }))
  mocks.checkPublish.mockImplementationOnce(() => new Promise(resolve => { currentFinish = resolve }))
  const wrapper = mount(VersionDetailView, { global: { stubs, directives: { loading: {} } } })
  await flushPromises()
  const button = (text: string) => wrapper.findAll('button').find(node => node.text() === text)!
  await button('发布').trigger('click')
  await button('取消').trigger('click')
  await button('发布').trigger('click')
  oldFinish({ passed: true, checks: [{ type: 'OLD', passed: true, message: 'stale allowed' }] })
  await flushPromises()
  expect(wrapper.text()).not.toContain('stale allowed')
  expect(button('确认发布').attributes('disabled')).toBeDefined()
  currentFinish({ passed: false, checks: [{ type: 'CURRENT', passed: false, message: 'current blocked' }] })
  await flushPromises()
  expect(wrapper.text()).toContain('current blocked')
  expect(button('确认发布').attributes('disabled')).toBeDefined()
  expect(mocks.listVersionRequirements).not.toHaveBeenCalled()
  wrapper.unmount()
})
