import { createSSRApp, defineComponent, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { describe, expect, it } from 'vitest'
import RoleActions from '@/components/RoleActions.vue'
import type { RoleItem } from '@/types/system'

const ElButtonStub = defineComponent({
  setup(_props, { slots }) {
    return () => h('button', slots.default?.())
  },
})

function role(isSystem: boolean): RoleItem {
  return {
    id: isSystem ? 1 : 2,
    code: isSystem ? 'SUPER_ADMIN' : 'CUSTOM_ROLE',
    name: isSystem ? '超级管理员' : '自定义角色',
    data_scope: isSystem ? 'ALL' : 'SELF',
    enabled: true,
    is_system: isSystem,
    revision: 1,
    permission_ids: [],
  }
}

async function renderActions(item: RoleItem): Promise<string> {
  const app = createSSRApp(RoleActions, { role: item })
  app.component('el-button', ElButtonStub)
  return renderToString(app)
}

describe('role action visibility', () => {
  it('shows view permissions but hides mutating actions for system roles', async () => {
    const html = await renderActions(role(true))
    expect(html).toContain('查看权限')
    expect(html).not.toContain('配置权限')
    expect(html).not.toContain('编辑')
    expect(html).not.toContain('删除')
  })

  it('shows edit, configure permissions, and delete actions for custom roles', async () => {
    const html = await renderActions(role(false))
    expect(html).toContain('编辑')
    expect(html).toContain('配置权限')
    expect(html).not.toContain('查看权限')
    expect(html).toContain('删除')
  })
})
