import axios, { type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it } from 'vitest'

let lastRequest: InternalAxiosRequestConfig | null = null

axios.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
  lastRequest = config
  return { data: {}, status: 200, statusText: 'ok', headers: {}, config }
}

const { updateUser, updateUserRoles, updateUserStatus } = await import('@/api/users')

beforeEach(() => {
  lastRequest = null
  localStorage.clear()
})

describe('user administration API boundaries', () => {
  it('updates profile fields without role_ids', async () => {
    await updateUser(7, {
      display_name: '更新名称',
      email: null,
      mobile: null,
      revision: 4,
    })
    expect(lastRequest?.method).toBe('patch')
    expect(lastRequest?.url).toBe('/users/7')
    expect(JSON.parse(String(lastRequest?.data))).toEqual({
      display_name: '更新名称',
      email: null,
      mobile: null,
      revision: 4,
    })
    expect(JSON.parse(String(lastRequest?.data))).not.toHaveProperty('role_ids')
  })

  it('uses dedicated role and status APIs with the current revision', async () => {
    await updateUserRoles(7, [1, 3], 5)
    expect(lastRequest?.method).toBe('put')
    expect(lastRequest?.url).toBe('/users/7/roles')
    expect(JSON.parse(String(lastRequest?.data))).toEqual({ role_ids: [1, 3], revision: 5 })

    await updateUserStatus(7, 'DISABLED', 6)
    expect(lastRequest?.method).toBe('patch')
    expect(lastRequest?.url).toBe('/users/7/status')
    expect(JSON.parse(String(lastRequest?.data))).toEqual({ status: 'DISABLED', revision: 6 })
  })
})
