import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { formatLocalDateTime } from '@/utils/dates'
import type { ReleaseItem } from '@/types/domain'

const mocks = vi.hoisted(() => ({ getRelease: vi.fn(), getVersion: vi.fn(), can: vi.fn(), route: { params: { id: '123' } } }))
vi.mock('@/api/releases', () => ({ getRelease: mocks.getRelease }))
vi.mock('@/api/versions', () => ({ getVersion: mocks.getVersion }))
vi.mock('@/composables/usePermission', () => ({ usePermission: () => ({ can: mocks.can }) }))
vi.mock('vue-router', () => ({ useRoute: () => mocks.route }))
import ReleaseDetailView from './ReleaseDetailView.vue'

const release: ReleaseItem = {
  id: 123, version_id: 456, result: 'SUCCESS', revision: 1,
  released_at: '2026-10-01T01:00:00Z', created_at: '2026-10-01T02:00:00Z', created_by: 8,
  release_notes: '完整发布说明\n第二行 https://example.com/' + 'long-path'.repeat(30), rollback_notes: '历史回滚说明\n保留原文',
}

function view() {
  return mount(ReleaseDetailView, { global: {
    directives: { loading: () => {} },
    stubs: {
      RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      'el-button': { template: '<button><slot /></button>' },
    },
  } })
}

beforeEach(() => {
  vi.resetAllMocks()
  mocks.route = reactive({ params: { id: '123' } })
  mocks.can.mockReturnValue(false)
  mocks.getRelease.mockResolvedValue({ ...release })
  mocks.getVersion.mockResolvedValue({ version_no: 'V1.6.0', name: '版本名称' })
})

describe('read-only release detail', () => {
  it('renders every release field in full without a version permission or API request', async () => {
    const wrapper = view()
    await flushPromises()
    for (const text of ['#123', '版本 #456', '成功', '用户 #8', formatLocalDateTime(release.released_at), formatLocalDateTime(release.created_at)]) {
      expect(wrapper.text()).toContain(text)
    }
    expect(wrapper.findAll('.release-notes').map(node => node.text())).toEqual([release.release_notes, release.rollback_notes])
    expect(wrapper.find('a[href="/versions/456"]').exists()).toBe(false)
    expect(mocks.getVersion).not.toHaveBeenCalled()
    expect(wrapper.findAll('button')).toHaveLength(0)
    expect(mocks.getRelease).toHaveBeenCalledWith(123)
    wrapper.unmount()
  })

  it('renders null creator and rollback notes as 系统 and —', async () => {
    mocks.getRelease.mockResolvedValue({ ...release, created_by: null, rollback_notes: null })
    const wrapper = view()
    await flushPromises()
    expect(wrapper.text()).toContain('系统')
    expect(wrapper.findAll('.release-notes')[1]!.text()).toBe('—')
    wrapper.unmount()
  })

  it('links the version and loads its display information only with version permission', async () => {
    mocks.can.mockReturnValue(true)
    const wrapper = view()
    await flushPromises()
    expect(wrapper.get('a[href="/versions/456"]').text()).toBe('版本 #456')
    expect(wrapper.text()).toContain('V1.6.0 · 版本名称')
    expect(mocks.getVersion).toHaveBeenCalledWith(456)
    wrapper.unmount()
  })

  it.each([403, 404, 'network'])('keeps the release visible when optional version metadata fails (%s)', async status => {
    mocks.can.mockReturnValue(true)
    mocks.getVersion.mockRejectedValue(status === 'network' ? new Error('network') : { response: { status } })
    const wrapper = view()
    await flushPromises()
    expect(wrapper.text()).toContain('版本 #456')
    expect(wrapper.text()).toContain(release.release_notes)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('uses the same safe 404 message for absent or inaccessible releases', async () => {
    mocks.getRelease.mockRejectedValue({ response: { status: 404, data: { message: 'private existence detail' } } })
    const wrapper = view()
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('发布记录不存在或不可访问')
    expect(wrapper.text()).not.toContain('private existence detail')
    expect(mocks.getVersion).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it.each([500, 'network'])('retries the release GET after a normal load failure (%s)', async status => {
    mocks.getRelease.mockRejectedValueOnce(status === 'network' ? new Error('network') : { response: { status } })
    const wrapper = view()
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('发布记录加载失败')
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(mocks.getRelease).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('用户 #8')
    wrapper.unmount()
  })

  it('ignores an old release response after navigating to another release', async () => {
    let finish!: (value: ReleaseItem) => void
    mocks.getRelease.mockImplementationOnce(() => new Promise<ReleaseItem>(resolve => { finish = resolve }))
    const wrapper = view()
    mocks.route.params.id = '124'
    mocks.getRelease.mockResolvedValue({ ...release, id: 124, version_id: 457 })
    await flushPromises()
    finish(release)
    await flushPromises()
    expect(wrapper.text()).toContain('#124')
    expect(wrapper.text()).toContain('版本 #457')
    expect(wrapper.text()).not.toContain('版本 #456')
    wrapper.unmount()
  })

  it('ignores optional metadata from the previously viewed release', async () => {
    mocks.can.mockReturnValue(true)
    let finish!: (value: { version_no: string; name: string }) => void
    mocks.getVersion.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    const wrapper = view()
    await flushPromises()
    mocks.getRelease.mockResolvedValue({ ...release, id: 124, version_id: 457 })
    mocks.getVersion.mockResolvedValue({ version_no: 'V1.7.0', name: '最新版本' })
    mocks.route.params.id = '124'
    await flushPromises()
    finish({ version_no: 'V1.6.0', name: '旧版本' })
    await flushPromises()
    expect(wrapper.text()).toContain('V1.7.0 · 最新版本')
    expect(wrapper.text()).not.toContain('旧版本')
    wrapper.unmount()
  })
})
