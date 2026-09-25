import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  logout: vi.fn(),
  auth: {
    user: {
      username: 'member.long.name',
      display_name: '普通成员',
      email: 'member@example.com' as string | null,
      status: 'ACTIVE',
      data_scope: 'SELF',
    },
  },
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push, replace: mocks.replace }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ ...mocks.auth, logout: mocks.logout }) }))

import ProfileView from '@/views/profile/ProfileView.vue'

const stubs = {
  'el-card': { template: '<section><slot name="header" /><slot /></section>' },
  'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>', emits: ['click'] },
}

function view() {
  return mount(ProfileView, { global: { stubs } })
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.auth.user.email = 'member@example.com'
  mocks.logout.mockResolvedValue(undefined)
})

describe('personal center', () => {
  it('renders current account details without loading administrator user APIs', () => {
    const wrapper = view()
    expect(wrapper.text()).toContain('个人中心')
    for (const value of ['普通成员', 'member.long.name', 'member@example.com', '启用', '我的数据']) {
      expect(wrapper.text()).toContain(value)
    }
    expect(wrapper.text()).not.toContain('permission_codes')
  })

  it('shows a neutral placeholder when email is null', () => {
    mocks.auth.user.email = null
    expect(view().text()).toContain('未设置')
  })

  it('opens regular password change from the profile', async () => {
    const wrapper = view()
    await wrapper.findAll('button').find((button) => button.text() === '修改密码')!.trigger('click')
    expect(mocks.push).toHaveBeenCalledWith('/change-password?from=profile')
  })

  it('logs out and returns to login', async () => {
    const wrapper = view()
    await wrapper.findAll('button').find((button) => button.text() === '退出登录')!.trigger('click')
    await flushPromises()
    expect(mocks.logout).toHaveBeenCalledOnce()
    expect(mocks.replace).toHaveBeenCalledWith('/login')
  })
})
