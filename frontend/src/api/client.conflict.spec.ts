import axios, { type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const messages = vi.hoisted(() => ({ warning: vi.fn(), error: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: messages }))

axios.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
  const code = Number(config.params?.code ?? 40910)
  const response = { status: Number(config.params?.status ?? 409), statusText: 'Conflict', data: { code, message: '业务条件不满足' }, headers: {}, config }
  return Promise.reject({ isAxiosError: true, config, response })
}

const { api } = await import('./client')

beforeEach(() => {
  messages.warning.mockClear()
  messages.error.mockClear()
  localStorage.clear()
})

describe('409 interceptor separates revision and business conflicts', () => {
  it('keeps generic forbidden feedback unless a form explicitly handles the reason', async () => {
    await expect(api.get('/probe', { params: { status: 403 } })).rejects.toMatchObject({ response: { status: 403 } })
    expect(messages.error).toHaveBeenCalledExactlyOnceWith('你没有权限执行该操作')
    messages.error.mockClear()
    await expect(api.get('/probe', { params: { status: 403 }, skipForbiddenAlert: true })).rejects.toMatchObject({ response: { data: { message: '业务条件不满足' } } })
    expect(messages.error).not.toHaveBeenCalled()
  })
  it('uses revision wording only for 40910', async () => {
    await expect(api.get('/probe', { params: { code: 40910 } })).rejects.toMatchObject({ response: { status: 409 } })
    expect(messages.warning).toHaveBeenCalledExactlyOnceWith('服务器版本已变化，请查看冲突详情')
  })

  it('keeps the server business message for other 409 codes', async () => {
    await expect(api.get('/probe', { params: { code: 40923 } })).rejects.toMatchObject({ response: { status: 409 } })
    expect(messages.warning).toHaveBeenCalledExactlyOnceWith('业务条件不满足')
  })

  it('suppresses only the revision warning when a local dialog handles 40910', async () => {
    await expect(api.get('/probe', { params: { code: 40910 }, skipRevisionConflictAlert: true })).rejects.toMatchObject({ response: { status: 409 } })
    expect(messages.warning).not.toHaveBeenCalled()
  })

  it.each([40911, 40913, 40923, 40930, 40931, 40932, 40933])('keeps the business message for %i with revision alerts disabled', async (code) => {
    await expect(api.get('/probe', { params: { code }, skipRevisionConflictAlert: true })).rejects.toMatchObject({ response: { status: 409 } })
    expect(messages.warning).toHaveBeenCalledExactlyOnceWith('业务条件不满足')
  })

  it.each([
    { code: 40910 },
    { code: 40923 },
    { code: 40910, skipRevisionConflictAlert: true },
    { code: 40923, skipRevisionConflictAlert: true },
  ])('preserves skipConflictAlert for all conflicts: %j', async ({ code, skipRevisionConflictAlert }) => {
    await expect(api.get('/probe', { params: { code }, skipConflictAlert: true, skipRevisionConflictAlert })).rejects.toMatchObject({ response: { status: 409 } })
    expect(messages.warning).not.toHaveBeenCalled()
  })
})
