/** @vitest-environment jsdom */

import { createSSRApp, defineComponent, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import type { DataScope } from '@/types/auth'

vi.mock('vue-router', () => ({
  useRouter: () => ({ replace: vi.fn() }),
}))

vi.mock('@/components/MobileBottomNav.vue', () => ({
  default: defineComponent({ render: () => null }),
}))

const { default: AppLayout } = await import('@/layouts/AppLayout.vue')

const RouterLinkStub = defineComponent({
  props: { to: { type: String, required: true } },
  setup(props, { slots }) {
    return () => h('a', { href: props.to }, slots.default?.())
  },
})

async function renderLayout(permissionCodes: string[], dataScope: DataScope): Promise<string> {
  const pinia = createPinia()
  const auth = useAuthStore(pinia)
  auth.$patch({
    accessToken: 'test-token',
    initialized: true,
    user: {
      id: 1,
      username: 'navigation-user',
      display_name: 'Navigation User',
      email: null,
      status: 'ACTIVE',
      revision: 1,
      role_ids: [],
      permission_codes: permissionCodes,
      data_scope: dataScope,
      must_change_password: false,
    },
  })

  const app = createSSRApp(AppLayout)
  app.use(pinia)
  app.component('router-link', RouterLinkStub)
  app.component('router-view', defineComponent({ render: () => null }))
  app.component('el-button', defineComponent({ render: () => null }))
  return renderToString(app)
}

describe('application navigation permissions', () => {
  it('shows role management for ALL-scope role viewers', async () => {
    const html = await renderLayout(['sys.role.view'], 'ALL')
    expect(html).toContain('href="/admin/roles"')
  })

  it('shows role management for ALL-scope role managers', async () => {
    const html = await renderLayout(['sys.role.manage'], 'ALL')
    expect(html).toContain('href="/admin/roles"')
  })

  it('hides role management without view or manage permission', async () => {
    const html = await renderLayout(['sys.user.view'], 'ALL')
    expect(html).not.toContain('href="/admin/roles"')
  })

  it('hides role management from SELF-scope role viewers', async () => {
    const html = await renderLayout(['sys.role.view'], 'SELF')
    expect(html).not.toContain('href="/admin/roles"')
  })

  it('keeps single-string menu permissions unchanged', async () => {
    const visible = await renderLayout(['dashboard.view'], 'SELF')
    const hidden = await renderLayout([], 'SELF')
    expect(visible).toContain('href="/"')
    expect(hidden).not.toContain('href="/"')
  })
})
