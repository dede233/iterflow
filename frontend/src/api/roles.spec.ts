import axios, { type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
  ElMessageBox: { alert: vi.fn(() => Promise.resolve()) },
}))

let lastRequest: InternalAxiosRequestConfig | null = null
let nextResponse: { status: number; data: unknown } = { status: 200, data: {} }

axios.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
  lastRequest = config
  const response = { data: nextResponse.data, status: nextResponse.status, statusText: 'ok', headers: {}, config }
  if (nextResponse.status >= 200 && nextResponse.status < 300) return response
  return Promise.reject({ isAxiosError: true, config, response })
}

const {
  createRole,
  deleteRole,
  getRole,
  listPermissions,
  updateRole,
  updateRolePermissions,
} = await import('@/api/roles')

beforeEach(() => {
  lastRequest = null
  nextResponse = { status: 200, data: {} }
  localStorage.clear()
})

describe('role management API DTO mapping', () => {
  it('creates and updates configurable roles', async () => {
    await createRole({ code: 'CUSTOM', name: '自定义角色', data_scope: 'SELF', permission_ids: [1] })
    expect(lastRequest?.method).toBe('post')
    expect(lastRequest?.url).toBe('/roles')

    await updateRole(7, { name: '更新角色', enabled: false, revision: 3 })
    expect(lastRequest?.method).toBe('patch')
    expect(lastRequest?.url).toBe('/roles/7')
    expect(JSON.parse(String(lastRequest?.data))).toMatchObject({ name: '更新角色', revision: 3 })
  })

  it('loads details and deletes a custom role', async () => {
    await getRole(8)
    expect(lastRequest?.method).toBe('get')
    expect(lastRequest?.url).toBe('/roles/8')

    nextResponse = { status: 200, data: { id: 8, deleted: true } }
    await expect(deleteRole(8)).resolves.toEqual({ id: 8, deleted: true })
    expect(lastRequest?.method).toBe('delete')
    expect(lastRequest?.url).toBe('/roles/8')
  })

  it('loads read-only catalog metadata and writes permissions with the current revision', async () => {
    nextResponse = {
      status: 200,
      data: [
        {
          id: 3,
          code: 'sys.role.manage',
          name: '角色管理',
          category: 'BUTTON',
          group: 'Role / 角色权限',
          sensitive: true,
        },
      ],
    }
    await expect(listPermissions()).resolves.toMatchObject([
      { id: 3, group: 'Role / 角色权限', sensitive: true },
    ])
    expect(lastRequest?.method).toBe('get')
    expect(lastRequest?.url).toBe('/roles/permissions')

    nextResponse = { status: 200, data: {} }
    await updateRolePermissions(7, [3, 1], 9)
    expect(lastRequest?.method).toBe('put')
    expect(lastRequest?.url).toBe('/roles/7/permissions')
    expect(JSON.parse(String(lastRequest?.data))).toEqual({
      permission_ids: [3, 1],
      revision: 9,
    })
  })
})
