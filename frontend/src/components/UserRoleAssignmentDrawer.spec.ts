import { createSSRApp, defineComponent, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { mount } from '@vue/test-utils'
import { ElCheckbox, ElCheckboxGroup } from 'element-plus'
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
    assignable: true,
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
    assignable: true,
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
    assignable: true,
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
  email_verification_status: 'NO_EMAIL',
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

  it('preserves existing historical roles on save and supports removing them', async () => {
    const assignedRole: RoleItem = {
      ...roles[2], id: 4, code: 'LEGACY_DESIGNER', name: '历史设计角色', assignable: false,
    }
    const unassignedRole: RoleItem = {
      ...assignedRole, id: 5, code: 'LEGACY_OPERATOR', name: '历史运营角色', enabled: true,
    }
    const wrapper = mount(UserRoleAssignmentDrawer, {
      props: {
        modelValue: true,
        user: { ...user, role_ids: [1, 2, 4] },
        roles: [...roles, assignedRole, unassignedRole],
        operatorIsSuperAdmin: false,
      },
      global: {
        components: {
          'el-drawer': PassThrough,
          'el-alert': PassThrough,
          'el-checkbox-group': ElCheckboxGroup,
          'el-checkbox': ElCheckbox,
          'el-tag': PassThrough,
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })
    expect(wrapper.text()).not.toContain(unassignedRole.name)
    const historicalOption = wrapper.findAll('.role-option').find((option) => option.text().includes(assignedRole.name))!
    const historicalCheckbox = historicalOption.get<HTMLInputElement>('input[type="checkbox"]')
    const saveButton = wrapper.findAll('button').find((button) => button.text() === '保存角色')!

    expect(historicalOption.text()).toContain('历史角色')
    expect(historicalCheckbox.element.checked).toBe(true)
    await saveButton.trigger('click')
    expect(wrapper.emitted('save')).toEqual([[[1, 2, 4]]])

    await historicalCheckbox.setValue(false)
    await saveButton.trigger('click')
    expect(wrapper.emitted('save')).toEqual([[[1, 2, 4]], [[1, 2]]])

    await wrapper.setProps({ user })
    expect(wrapper.text()).not.toContain(assignedRole.name)
    wrapper.unmount()
  })
})
