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
    expect(router.currentRoute.value.meta.permission).toEqual([
      'sys.role.view',
      'sys.role.manage',
    ])
  })
})
