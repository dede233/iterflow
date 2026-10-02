import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ElementPlus, { ElDatePicker, ElDrawer, ElFormItem, ElInput, ElInputNumber, ElMessage, ElPagination, ElSelect, ElTable } from 'element-plus'

const mocks = vi.hoisted(() => ({ requirements: vi.fn(), versions: vi.fn(), releases: vi.fn(), push: vi.fn(), mobile: false, create: false }))
vi.mock('@/api/requirements', () => ({ listRequirements: mocks.requirements, createRequirement: vi.fn() }))
vi.mock('@/api/versions', () => ({ listVersions: mocks.versions, createVersion: vi.fn() }))
vi.mock('@/api/releases', () => ({ listReleases: mocks.releases }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))
vi.mock('@/composables/useResponsive', () => ({ useResponsive: () => ({ isMobile: mocks.mobile }) }))
vi.mock('@/composables/usePermission', () => ({ usePermission: () => ({ can: (code: string) => mocks.create && code.endsWith('.create') }) }))

import RequirementListView from './requirement/RequirementListView.vue'
import VersionListView from './version/VersionListView.vue'
import ReleaseListView from './release/ReleaseListView.vue'
import ListFilterPanel from '@/components/ui/ListFilterPanel.vue'

const configs = [
  { name: 'Requirement', component: RequirementListView, api: mocks.requirements, keyword: '编号 / 标题', labels: ['关键词', '状态', '优先级', '来源', '版本 ID', '负责人 ID'], row: { id: 1, title: 'latest result', requirement_no: 'REQ-1', status: 'DRAFT', priority: 'P1', source: 'DIRECT' }, params: { keyword: 'Search', status: 'CONFIRMED', priority: 'P1', source: 'FEEDBACK', current_version_id: 42, owner_id: 8 } },
  { name: 'Version', component: VersionListView, api: mocks.versions, keyword: '版本号 / 名称', labels: ['关键词', '状态', '计划上线日期', '负责人 ID'], row: { id: 1, name: 'latest result', version_no: 'V1', status: 'RELEASED' }, params: { keyword: 'Search', status: 'RELEASED', planned_release_from: '2026-10-01', planned_release_to: '2026-10-03', owner_id: 8 } },
  { name: 'Release', component: ReleaseListView, api: mocks.releases, keyword: null, labels: ['版本 ID'], row: { id: 1, version_id: 42, result: 'SUCCESS', release_notes: 'latest result' }, params: { version_id: 42 } },
] as const

beforeEach(() => {
  vi.clearAllMocks()
  mocks.mobile = false
  mocks.create = false
  for (const config of configs) config.api.mockReset().mockResolvedValue({ items: [config.row], total: 100 })
})

async function view(config: typeof configs[number], mobile = false) {
  mocks.mobile = mobile
  const renderLoading = (el: HTMLElement, binding: { value: boolean }) => el.setAttribute('data-loading', String(binding.value))
  const wrapper = mount(config.component, { global: {
    plugins: [ElementPlus],
    directives: { loading: { mounted: renderLoading, updated: renderLoading } },
    stubs: {
      RequirementCreateView: { name: 'RequirementCreateView', template: '<button @click="$emit(\'created\', 7)">完成创建</button>', emits: ['created'] },
      VersionCreateView: { name: 'VersionCreateView', template: '<button @click="$emit(\'created\', 7)">完成创建</button>', emits: ['created'] },
    },
  } })
  await flushPromises()
  if (mobile) {
    await wrapper.findAll('button').find(button => button.text() === '筛选')!.trigger('click')
    await flushPromises()
    expect(wrapper.findComponent(ElDrawer).props('modelValue')).toBe(true)
  }
  return wrapper
}

async function fill(wrapper: VueWrapper, config: typeof configs[number]) {
  if (config.keyword) wrapper.findAllComponents(ElInput).find(input => input.props('placeholder') === config.keyword)!.vm.$emit('update:modelValue', ' Search ')
  const selects = wrapper.findAllComponents(ElSelect)
  if (config.name === 'Requirement') {
    selects[0]!.vm.$emit('update:modelValue', 'CONFIRMED')
    selects[1]!.vm.$emit('update:modelValue', 'P1')
    selects[2]!.vm.$emit('update:modelValue', 'FEEDBACK')
    wrapper.findAllComponents(ElInputNumber)[0]!.vm.$emit('update:modelValue', 42)
    wrapper.findAllComponents(ElInputNumber)[1]!.vm.$emit('update:modelValue', 8)
  } else if (config.name === 'Version') {
    selects[0]!.vm.$emit('update:modelValue', 'RELEASED')
    wrapper.findComponent(ElDatePicker).vm.$emit('update:modelValue', ['2026-10-01', '2026-10-03'])
    wrapper.findComponent(ElInputNumber).vm.$emit('update:modelValue', 8)
  } else wrapper.findComponent(ElInputNumber).vm.$emit('update:modelValue', 42)
  await flushPromises()
}

function search(wrapper: VueWrapper) { wrapper.findComponent(ListFilterPanel).vm.$emit('search') }

for (const config of configs) {
  describe(`${config.name} filters`, () => {
    it.each([false, true])('desktop/mobile=%s: query, reset and pagination preserve exact parameters', async mobile => {
      const wrapper = await view(config, mobile)
      expect(config.api).toHaveBeenCalledTimes(1)
      expect(config.api.mock.calls[0]![0].page).toBe(1)
      for (const [key, value] of Object.entries(config.api.mock.calls[0]![0])) {
        if (!['page', 'page_size'].includes(key)) expect(value).toBeUndefined()
      }
      const labels = wrapper.findAllComponents(ElFormItem).map(item => item.props('label')).filter(Boolean)
      expect(labels).toEqual(config.labels)
      for (const number of wrapper.findAllComponents(ElInputNumber)) expect(number.props('min')).toBe(1)
      await fill(wrapper, config)
      wrapper.findComponent(ElPagination).vm.$emit('current-change', 3)
      await flushPromises()
      const expected = { ...config.params, page: 3, page_size: 20 }
      expect(config.api).toHaveBeenLastCalledWith(expected)
      search(wrapper)
      await flushPromises()
      expect(config.api).toHaveBeenLastCalledWith({ ...expected, page: 1 })
      if (mobile) expect(wrapper.findComponent(ElDrawer).props('modelValue')).toBe(false)
      wrapper.findComponent(ListFilterPanel).vm.$emit('reset')
      await flushPromises()
      const reset = config.api.mock.calls.at(-1)![0]
      expect(reset.page).toBe(1)
      for (const [key, value] of Object.entries(reset)) if (!['page', 'page_size'].includes(key)) expect(value).toBeUndefined()
      wrapper.unmount()
    })

    it('retries with current filters after a load failure', async () => {
      const wrapper = await view(config)
      await fill(wrapper, config)
      config.api.mockRejectedValueOnce(new Error('offline'))
      search(wrapper)
      await flushPromises()
      expect(wrapper.get('[role="alert"]').text()).toContain('加载失败')
      const failedParams = config.api.mock.calls.at(-1)![0]
      await wrapper.findAll('button').find(button => button.text() === '重新加载')!.trigger('click')
      await flushPromises()
      expect(config.api).toHaveBeenLastCalledWith(failedParams)
      expect(wrapper.find('[role="alert"]').exists()).toBe(false)
      wrapper.unmount()
    })

    it('ignores stale success, stale error and stale loading completion', async () => {
      const wrapper = await view(config)
      let resolveA!: (value: unknown) => void
      let rejectC!: (error: Error) => void
      let resolveD!: (value: unknown) => void
      config.api.mockImplementationOnce(() => new Promise(resolve => { resolveA = resolve }))
      search(wrapper)
      config.api.mockResolvedValueOnce({ items: [{ ...config.row, title: 'newest B', name: 'newest B', release_notes: 'newest B' }], total: 2 })
      search(wrapper)
      await flushPromises()
      resolveA({ items: [{ ...config.row, title: 'stale A', name: 'stale A', release_notes: 'stale A' }], total: 1 })
      await flushPromises()
      expect(wrapper.text()).toContain('newest B')
      expect(wrapper.text()).not.toContain('stale A')
      config.api.mockImplementationOnce(() => new Promise((_, reject) => { rejectC = reject }))
      search(wrapper)
      config.api.mockImplementationOnce(() => new Promise(resolve => { resolveD = resolve }))
      search(wrapper)
      await flushPromises()
      expect(wrapper.findComponent(ElTable).attributes('data-loading')).toBe('true')
      rejectC(new Error('old failure'))
      await flushPromises()
      expect(wrapper.find('[role="alert"]').exists()).toBe(false)
      expect(wrapper.findComponent(ElTable).attributes('data-loading')).toBe('true')
      resolveD({ items: [config.row], total: 100 })
      await flushPromises()
      expect(wrapper.findComponent(ElTable).attributes('data-loading')).toBe('false')
      wrapper.unmount()
    })

    it('does not send invalid numeric IDs or call other list APIs', async () => {
      const wrapper = await view(config)
      for (const field of wrapper.findAllComponents(ElInputNumber)) field.vm.$emit('update:modelValue', 0)
      search(wrapper)
      await flushPromises()
      const params = config.api.mock.calls.at(-1)![0]
      for (const key of ['owner_id', 'current_version_id', 'version_id']) expect(params[key]).toBeUndefined()
      for (const other of configs) if (other !== config) expect(other.api).not.toHaveBeenCalled()
      wrapper.unmount()
    })
  })
}

it('prevents an inverted Version date range from reaching the API', async () => {
  const warning = vi.spyOn(ElMessage, 'warning')
  const config = configs[1]
  const wrapper = await view(config)
  wrapper.findComponent(ElDatePicker).vm.$emit('update:modelValue', ['2026-10-03', '2026-10-01'])
  await flushPromises()
  search(wrapper)
  await flushPromises()
  expect(config.api).toHaveBeenCalledTimes(1)
  expect(warning).toHaveBeenCalledWith('计划上线结束日期不能早于开始日期')
  wrapper.unmount()
  warning.mockRestore()
  ElMessage.closeAll()
})

it.each([configs[0], configs[1]])('keeps $name creation refresh before detail navigation', async config => {
  mocks.create = true
  const wrapper = await view(config)
  await wrapper.findAll('button').find(button => button.text().includes('新建'))!.trigger('click')
  await flushPromises()
  const create = wrapper.findComponent(config.name === 'Requirement' ? { name: 'RequirementCreateView' } : { name: 'VersionCreateView' })
  create.vm.$emit('created', 7)
  await flushPromises()
  expect(config.api).toHaveBeenCalledTimes(2)
  expect(mocks.push).toHaveBeenCalledWith(config.name === 'Requirement' ? '/requirements/7' : '/versions/7')
  expect(config.api.mock.invocationCallOrder[1]).toBeLessThan(mocks.push.mock.invocationCallOrder[0]!)
  wrapper.unmount()
})
