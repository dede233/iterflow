import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  query: { from: 'profile' as string | undefined },
  auth: { mustChangePassword: false },
  changePassword: vi.fn(),
  success: vi.fn(),
  warning: vi.fn(),
  error: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: mocks.query }),
  useRouter: () => ({ replace: mocks.replace }),
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get mustChangePassword() { return mocks.auth.mustChangePassword },
    changePassword: mocks.changePassword,
  }),
}))
vi.mock('element-plus', () => ({
  ElMessage: { success: mocks.success, warning: mocks.warning, error: mocks.error },
}))

import ChangePasswordView from '@/views/auth/ChangePasswordView.vue'

const stubs = {
  'el-card': { template: '<div><slot /></div>' },
  'el-form': { template: '<form @submit.prevent="$emit(\'submit\', $event)"><slot /></form>', emits: ['submit'] },
  'el-form-item': { template: '<div><slot /></div>' },
  'el-input': {
    props: ['modelValue'],
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    emits: ['update:modelValue'],
  },
  'el-button': { props: ['nativeType'], template: '<button :type="nativeType || \'button\'"><slot /></button>' },
}

function view() {
  return mount(ChangePasswordView, { global: { stubs } })
}

async function submitValidPassword(wrapper: ReturnType<typeof view>): Promise<void> {
  const inputs = wrapper.findAll('input')
  await inputs[0].setValue('current-pass')
  await inputs[1].setValue('new-password-123')
  await inputs[2].setValue('new-password-123')
  await wrapper.find('form').trigger('submit')
  await flushPromises()
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.auth.mustChangePassword = false
  mocks.query.from = 'profile'
  mocks.changePassword.mockImplementation(async () => { mocks.auth.mustChangePassword = false })
})

describe('change password contexts', () => {
  it('shows the regular title and returns to the profile', async () => {
    const wrapper = view()
    expect(wrapper.text()).toContain('修改密码')
    expect(wrapper.text()).toContain('定期更新密码有助于保护账号安全。')
    expect(wrapper.text()).not.toContain('修改初始密码')
    await submitValidPassword(wrapper)
    expect(mocks.changePassword).toHaveBeenCalledWith('current-pass', 'new-password-123')
    expect(mocks.replace).toHaveBeenCalledWith('/profile')
  })

  it('keeps first-login wording and redirects to the dashboard after password change', async () => {
    mocks.auth.mustChangePassword = true
    const wrapper = view()
    expect(wrapper.text()).toContain('修改初始密码')
    expect(wrapper.text()).toContain('为保护账号安全，请先设置一个新密码。')
    await submitValidPassword(wrapper)
    expect(mocks.replace).toHaveBeenCalledWith('/')
  })

  it('returns to the dashboard for a regular password change without a profile origin', async () => {
    mocks.query.from = undefined
    const wrapper = view()
    await submitValidPassword(wrapper)
    expect(mocks.replace).toHaveBeenCalledWith('/')
  })
})
