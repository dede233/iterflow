import { createSSRApp, defineComponent, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { describe, expect, it } from 'vitest'
import DashboardOverviewContent from '@/components/DashboardOverviewContent.vue'
import type { DashboardOverview } from '@/types/dashboard'

const PassThrough = defineComponent({
  setup(_props, { slots }) {
    return () => h('div', [slots.header?.(), slots.default?.()])
  },
})

const RouterLinkStub = defineComponent({
  props: { to: { type: String, required: true } },
  setup(props, { slots }) {
    return () => h('a', { href: props.to }, slots.default?.())
  },
})

function completeOverview(): DashboardOverview {
  return {
    data_scope: 'ALL',
    activities: [],
    feedback: {
      pending_count: 3,
      total_count: 7,
      by_status: { NEW: 2, ACCEPTED: 1, REQUIREMENT_LINKED: 4 },
    },
    requirements: {
      active_count: 5,
      total_count: 9,
      by_status: { CONFIRMED: 1, PLANNED: 2, DEVELOPING: 2, DONE: 4 },
    },
    versions: {
      active_count: 2,
      total_count: 4,
      by_status: { PLANNING: 1, TESTING: 1, RELEASED: 2 },
      recent_active_versions: [
        {
          id: 12,
          version_no: 'V2.1.0',
          name: '协作增强',
          status: 'TESTING',
          planned_release_date: '2026-10-01',
          updated_at: '2026-09-23T08:00:00Z',
        },
      ],
    },
    releases: {
      total_count: 6,
      recent_releases: [
        {
          id: 21,
          version_id: 11,
          version_no: 'V2.0.0',
          version_name: '权限基线',
          released_at: '2026-09-22T08:00:00Z',
          result: 'SUCCESS',
        },
      ],
    },
  }
}

async function renderOverview(overview: DashboardOverview): Promise<string> {
  const app = createSSRApp(DashboardOverviewContent, { overview })
  for (const name of ['el-row', 'el-col', 'el-card', 'el-tag', 'el-empty']) {
    app.component(name, PassThrough)
  }
  app.component('router-link', RouterLinkStub)
  return renderToString(app)
}

describe('dashboard overview content', () => {
  it('renders all authorized metrics, status sections, and recent records', async () => {
    const html = await renderOverview(completeOverview())
    expect(html).toContain('全部数据')
    expect(html).toContain('待处理反馈')
    expect(html).toContain('进行中需求')
    expect(html).toContain('活跃版本')
    expect(html).toContain('累计发布')
    expect(html).toContain('反馈状态')
    expect(html).toContain('需求状态')
    expect(html).toContain('版本状态')
    expect(html).toContain('href="/versions/12"')
    expect(html).toContain('V2.1.0')
    expect(html).toContain('V2.0.0')
    expect(html).toContain('href="/releases"')
  })

  it('hides an unauthorized domain instead of presenting zero data', async () => {
    const overview = completeOverview()
    overview.feedback = null
    overview.requirements = null
    const html = await renderOverview(overview)
    expect(html).not.toContain('待处理反馈')
    expect(html).not.toContain('反馈状态')
    expect(html).not.toContain('进行中需求')
    expect(html).not.toContain('需求状态')
    expect(html).toContain('活跃版本')
  })

  it('labels SELF scope and explains when every domain section is unavailable', async () => {
    const html = await renderOverview({
      data_scope: 'SELF',
      activities: [],
      feedback: null,
      requirements: null,
      versions: null,
      releases: null,
    })
    expect(html).toContain('我的数据')
    expect(html).toContain('当前账号没有可展示的业务概览数据')
    expect(html).not.toContain('待处理反馈')
  })

  it('renders explicit empty states for authorized version and release lists', async () => {
    const overview = completeOverview()
    overview.versions!.recent_active_versions = []
    overview.releases!.recent_releases = []
    const html = await renderOverview(overview)
    expect(html).toContain('暂无活跃版本')
    expect(html).toContain('暂无发布记录')
    expect(html).toContain('暂无最近活动')
    expect(html).toContain('待处理反馈')
  })

  it('renders safe activity fields with Chinese labels, local time and all four entity links', async () => {
    const overview = completeOverview()
    const createdAt = '2026-10-01T06:30:00Z'
    overview.activities = [
      { entity_type: 'FEEDBACK', entity_id: 101, action: 'CREATE', created_at: createdAt },
      { entity_type: 'REQUIREMENT', entity_id: 102, action: 'STATUS_CHANGE', created_at: createdAt },
      { entity_type: 'VERSION', entity_id: 103, action: 'VERSION_PUBLISH', created_at: createdAt },
      { entity_type: 'RELEASE', entity_id: 104, action: 'RELEASE_CREATE', created_at: createdAt },
    ]
    // Extra wire data is deliberately ignored by the rendering layer.
    Object.assign(overview.activities[0]!, {
      operator: { username: 'PRIVATE_USER', display_name: 'PRIVATE_DISPLAY' },
      before: { title: 'PRIVATE_BEFORE' }, after: { title: 'PRIVATE_AFTER' },
    })
    const html = await renderOverview(overview)
    for (const text of ['最近活动', '反馈 #101', '需求 #102', '版本 #103', '发布记录 #104', '创建', '变更状态', '发布版本', '创建发布记录']) expect(html).toContain(text)
    for (const path of ['/feedbacks/101', '/requirements/102', '/versions/103', '/releases/104']) expect(html).toContain(`href="${path}"`)
    expect(html).toContain(`datetime="${createdAt}"`)
    expect(html).toContain(new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(createdAt)))
    for (const text of ['操作人', '用户名', 'PRIVATE_USER', 'PRIVATE_DISPLAY', 'PRIVATE_BEFORE', 'PRIVATE_AFTER']) expect(html).not.toContain(text)
    expect(html).toContain('近期活跃版本')
    expect(html).toContain('近期发布')
  })

  it('keeps the existing fallback for unknown audit actions', async () => {
    const overview = completeOverview()
    overview.activities = [{ entity_type: 'REQUIREMENT', entity_id: 102, action: 'FUTURE_ACTION', created_at: '2026-10-01T06:30:00Z' }]
    const html = await renderOverview(overview)
    expect(html).toContain('未知操作（FUTURE_ACTION）')
    expect(html).toContain('href="/requirements/102"')
  })
})
