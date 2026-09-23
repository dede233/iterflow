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
  })
})
