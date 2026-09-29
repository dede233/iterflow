import axios, { type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const messages = vi.hoisted(() => ({ warning: vi.fn(), error: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: messages }))

axios.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
  const code = Number(config.params?.code ?? 40910)
  const response = { status: 409, statusText: 'Conflict', data: { code, message: '业务条件不满足' }, headers: {}, config }
  return Promise.reject({ isAxiosError: true, config, response })
}

const { api } = await import('./client')

beforeEach(() => {
  messages.warning.mockClear()
  localStorage.clear()
})

describe('409 interceptor separates revision and business conflicts', () => {
  it('uses revision wording only for 40910', async () => {
    await expect(api.get('/probe', { params: { code: 40910 } })).rejects.toMatchObject({ response: { status: 409 } })
    expect(messages.warning).toHaveBeenCalledExactlyOnceWith('服务器版本已变化，请查看冲突详情')
  })

  it('keeps the server business message for other 409 codes', async () => {
    await expect(api.get('/probe', { params: { code: 40923 } })).rejects.toMatchObject({ response: { status: 409 } })
    expect(messages.warning).toHaveBeenCalledExactlyOnceWith('业务条件不满足')
  })

  it('preserves skipConflictAlert for publish pre-checks', async () => {
    await expect(api.get('/probe', { params: { code: 40923 }, skipConflictAlert: true })).rejects.toMatchObject({ response: { status: 409 } })
    expect(messages.warning).not.toHaveBeenCalled()
  })
})
