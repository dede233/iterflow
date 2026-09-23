import { createSSRApp, defineComponent, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { describe, expect, it, vi } from 'vitest'
import dashboardSource from '@/views/dashboard/DashboardView.vue?raw'

vi.mock('element-plus', () => ({ ElMessage: { error: vi.fn() } }))
vi.mock('@/components/DashboardOverviewContent.vue', () => ({
  default: defineComponent({ render: () => h('div', 'overview content') }),
}))

const { default: DashboardView } = await import('@/views/dashboard/DashboardView.vue')

describe('dashboard view', () => {
  it('does not contain the former hardcoded dashboard figures or timeline', () => {
    expect(dashboardSource).not.toContain("{ label: '待处理反馈', value: 12 }")
    expect(dashboardSource).not.toContain("{ label: '进行中需求', value: 28 }")
    expect(dashboardSource).not.toContain("{ label: '当前版本', value: 'V1.0.1' }")
    expect(dashboardSource).not.toContain("{ label: '累计发布', value: 18 }")
    expect(dashboardSource).not.toContain('el-timeline')
  })

  it('shows an explicit loading state before the API resolves', async () => {
    const app = createSSRApp(DashboardView)
    app.component(
      'el-skeleton',
      defineComponent({
        inheritAttrs: false,
        setup() {
          return () => h('div', '正在加载系统概览')
        },
      }),
    )
    app.component('el-result', defineComponent({ render: () => null }))
    const html = await renderToString(app)
    expect(html).toContain('正在加载系统概览')
    expect(html).not.toContain('最近动态')
    expect(html).not.toContain('V1.0.1')
  })
})
