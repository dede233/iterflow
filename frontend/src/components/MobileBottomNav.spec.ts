import { createSSRApp, defineComponent, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { createPinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import MobileBottomNav from '@/components/MobileBottomNav.vue'
import { useAuthStore } from '@/stores/auth'

const RouterLinkStub = defineComponent({
  props: { to: { type: String, required: true } },
  setup(props, { slots }) {
    return () => h('a', { href: props.to }, slots.default?.())
  },
})

async function renderNav(permissionCodes: string[]): Promise<string> {
  const pinia = createPinia()
  useAuthStore(pinia).$patch({
    accessToken: 'test-token',
    initialized: true,
    user: {
      id: 2,
      username: 'member',
      display_name: '普通成员',
      email: null,
      status: 'ACTIVE',
      revision: 1,
      role_ids: [],
      permission_codes: permissionCodes,
      data_scope: 'SELF',
      must_change_password: false,
    },
  })
  const app = createSSRApp(MobileBottomNav)
  app.use(pinia)
  app.component('router-link', RouterLinkStub)
  return renderToString(app)
}

describe('mobile navigation', () => {
  it('keeps five existing links and adds My for an authorized user', async () => {
    const html = await renderNav(['dashboard.view', 'rd.feedback.view', 'rd.requirement.view', 'rd.version.view'])
    for (const path of ['/', '/feedbacks', '/requirements', '/versions', '/notifications', '/profile']) {
      expect(html).toContain(`href="${path}"`)
    }
    expect(html).toContain('我的')
    expect(html).toContain('消息')
  })

  it('still shows My and notifications to a MEMBER without business permissions', async () => {
    const html = await renderNav([])
    expect(html).toContain('href="/profile"')
    expect(html).toContain('href="/notifications"')
    expect(html).not.toContain('href="/feedbacks"')
  })
})
