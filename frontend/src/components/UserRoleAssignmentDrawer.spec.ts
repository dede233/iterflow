import { createSSRApp, defineComponent, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { describe, expect, it } from 'vitest'
import UserRoleAssignmentDrawer from '@/components/UserRoleAssignmentDrawer.vue'
import type { RoleItem, UserItem } from '@/types/system'

const PassThrough = defineComponent({
  props: { title: { type: String, default: '' } },
  setup(props, { slots }) {
    return () => h('div', [props.title, slots.default?.(), slots.footer?.()])
  },
})
const CheckboxStub = defineComponent({
  props: { disabled: Boolean },
  setup(props, { slots }) {
    return () => h('label', { 'data-disabled': String(props.disabled) }, slots.default?.())
  },
})

const roles: RoleItem[] = [
  {
    id: 1,
    code: 'SUPER_ADMIN',
    name: '超级管理员',
    data_scope: 'ALL',
    enabled: true,
    is_system: true,
    revision: 1,
    permission_ids: [],
  },
  {
    id: 2,
    code: 'MEMBER',
    name: '普通成员',
    data_scope: 'SELF',
    enabled: true,
    is_system: true,
    revision: 1,
    permission_ids: [],
  },
  {
    id: 3,
    code: 'DISABLED',
    name: '已禁用角色',
    data_scope: 'SELF',
    enabled: false,
    is_system: false,
    revision: 1,
    permission_ids: [],
  },
]
const user: UserItem = {
  id: 7,
  username: 'target',
  display_name: '目标用户',
  email: null,
  mobile: null,
  status: 'ACTIVE',
  revision: 4,
  role_ids: [1, 2],
}

async function renderDrawer(operatorIsSuperAdmin: boolean): Promise<string> {
  const app = createSSRApp(UserRoleAssignmentDrawer, {
    modelValue: true,
    user,
    roles,
    operatorIsSuperAdmin,
  })
  for (const name of ['el-drawer', 'el-alert', 'el-checkbox-group', 'el-tag', 'el-empty', 'el-button']) {
    app.component(name, PassThrough)
  }
  app.component('el-checkbox', CheckboxStub)
  return renderToString(app)
}

describe('user role assignment drawer', () => {
  it('marks SUPER_ADMIN high risk and locks it for a non-super operator', async () => {
    const html = await renderDrawer(false)
    expect(html).toContain('只有超级管理员可以授予或撤销超级管理员角色')
    expect(html).toContain('超级管理员 / 高风险')
    expect(html).toContain('data-disabled="true"')
    expect(html).not.toContain('已禁用角色')
  })

  it('allows a SUPER_ADMIN operator to interact with the high-risk role', async () => {
    const html = await renderDrawer(true)
    expect(html).not.toContain('只有超级管理员可以授予或撤销超级管理员角色')
    expect(html).toContain('data-disabled="false"')
    expect(html).toContain('保存角色')
  })
})
