/** @vitest-environment jsdom */

import { describe, expect, it } from 'vitest'
import { router } from '@/router'
import { useAuthStore } from '@/stores/auth'
import { pinia } from '@/stores/pinia'

describe('role management route permissions', () => {
  it('allows an ALL-scope user with sys.role.view to enter the role page', async () => {
    const auth = useAuthStore(pinia)
    auth.$patch({
      accessToken: 'test-token',
      initialized: true,
      user: {
        id: 1,
        username: 'role-viewer',
        display_name: 'Role Viewer',
        email: null,
        status: 'ACTIVE',
        revision: 1,
        role_ids: [],
        permission_codes: ['sys.role.view'],
        data_scope: 'ALL',
        must_change_password: false,
      },
    })

    await router.push('/admin/roles')

    expect(router.currentRoute.value.name).toBe('role-management')
    expect(window.location.hash).toBe('#/admin/roles')
    expect(router.currentRoute.value.meta.permission).toEqual([
      'sys.role.view',
      'sys.role.manage',
    ])
  })
})

describe('profile route', () => {
  it('lets a MEMBER with no business or administration permissions open their profile', async () => {
    const auth = useAuthStore(pinia)
    auth.$patch({
      accessToken: 'member-token',
      initialized: true,
      user: {
        id: 2,
        username: 'member',
        display_name: '普通成员',
        email: null,
        status: 'ACTIVE',
        revision: 1,
        role_ids: [],
        permission_codes: [],
        data_scope: 'SELF',
        must_change_password: false,
      },
    })

    await router.push('/profile')

    expect(router.currentRoute.value.name).toBe('profile')
    expect(router.currentRoute.value.meta.permission).toBeUndefined()
    expect(router.currentRoute.value.meta.requiresAllScope).toBeUndefined()
  })

  it('redirects an unauthenticated visitor to login', async () => {
    const auth = useAuthStore(pinia)
    await router.push('/notifications')
    auth.$patch({ accessToken: '', initialized: true, user: null })

    await router.push('/profile')

    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/profile')
  })
})
