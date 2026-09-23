import { createSSRApp, defineComponent, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { describe, expect, it } from 'vitest'
import PermissionAssignmentDrawer from '@/components/PermissionAssignmentDrawer.vue'
import type { PermissionItem, RoleItem } from '@/types/system'

const PassThrough = defineComponent({
  props: { title: { type: String, default: '' } },
  setup(props, { slots }) {
    return () => h('div', [props.title, slots.title?.(), slots.default?.(), slots.footer?.()])
  },
})
const ButtonStub = defineComponent({
  setup(_props, { slots }) {
    return () => h('button', slots.default?.())
  },
})

const permissions: PermissionItem[] = [
  {
    id: 1,
    code: 'rd.feedback.view',
    name: '反馈查看',
    category: 'BUTTON',
    group: 'Feedback / 反馈',
    sensitive: false,
    deprecated: false,
    replacement_code: null,
  },
  {
    id: 2,
    code: 'sys.role.manage',
    name: '角色管理',
    category: 'BUTTON',
    group: 'Role / 角色权限',
    sensitive: true,
    deprecated: false,
    replacement_code: null,
  },
  {
    id: 3,
    code: 'sys.role.edit',
    name: '角色权限编辑（已废弃）',
    category: 'BUTTON',
    group: 'Role / 角色权限',
    sensitive: false,
    deprecated: true,
    replacement_code: 'sys.role.manage',
  },
]

function role(isSystem: boolean): RoleItem {
  return {
    id: 1,
    code: isSystem ? 'SUPER_ADMIN' : 'CUSTOM',
    name: isSystem ? '超级管理员' : '自定义角色',
    data_scope: 'ALL',
    enabled: true,
    is_system: isSystem,
    revision: 3,
    permission_ids: [1, 2, 3],
  }
}

async function renderDrawer(item: RoleItem, readonly = false): Promise<string> {
  const app = createSSRApp(PermissionAssignmentDrawer, {
    modelValue: true,
    role: item,
    permissions,
    readonly,
  })
  for (const name of [
    'el-drawer',
    'el-alert',
    'el-collapse',
    'el-collapse-item',
    'el-checkbox',
    'el-checkbox-group',
    'el-tag',
    'el-empty',
  ]) {
    app.component(name, PassThrough)
  }
  app.component('el-button', ButtonStub)
  return renderToString(app)
}

describe('permission assignment drawer', () => {
  it('renders grouped permission codes and a risk marker', async () => {
    const html = await renderDrawer(role(false))
    expect(html).toContain('Feedback / 反馈')
    expect(html).toContain('Role / 角色权限')
    expect(html).toContain('sys.role.manage')
    expect(html).toContain('高风险')
    expect(html).toContain('保存权限')
  })

  it('renders system-role permissions read-only', async () => {
    const html = await renderDrawer(role(true))
    expect(html).toContain('系统角色为只读安全基线')
    expect(html).not.toContain('保存权限')
  })

  it('renders custom roles read-only when the caller cannot manage roles', async () => {
    const html = await renderDrawer(role(false), true)
    expect(html).toContain('当前账号仅有角色查看权限')
    expect(html).not.toContain('保存权限')
  })

  it('marks deprecated permissions and shows their replacement without converting them', async () => {
    const html = await renderDrawer(role(false))
    expect(html).toContain('已废弃')
    expect(html).toContain('替代权限：')
    expect(html).toContain('sys.role.manage')
  })
})
