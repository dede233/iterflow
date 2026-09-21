import axios, { type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// Silence Element Plus feedback so the 409/403 branch of the response
// interceptor resolves immediately instead of awaiting a real dialog.
vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
  ElMessageBox: { alert: vi.fn(() => Promise.resolve()) },
}))

let lastRequest: InternalAxiosRequestConfig | null = null
let nextResponse: { status: number; data: unknown } = { status: 200, data: {} }

axios.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
  lastRequest = config
  const { status, data } = nextResponse
  const response = { data, status, statusText: 'x', headers: {}, config }
  if (status >= 200 && status < 300) return response
  return Promise.reject({ isAxiosError: true, config, response })
}

const { createFeedback, changeFeedbackStatus, listFeedbacks } = await import('@/api/feedbacks')
const { availableStatusActions } = await import('@/constants/feedback')

beforeEach(() => {
  lastRequest = null
  nextResponse = { status: 200, data: {} }
  localStorage.clear()
})

describe('availableStatusActions (frozen human state machine)', () => {
  it('offers the four NEW transitions when the user may edit', () => {
    const targets = availableStatusActions('NEW', true).map((a) => a.target)
    expect(targets).toEqual(['ACCEPTED', 'DUPLICATE', 'CANNOT_REPRODUCE', 'CLOSED'])
  })

  it('never offers ACCEPTED -> NEW', () => {
    const targets = availableStatusActions('ACCEPTED', true).map((a) => a.target)
    expect(targets).toEqual(['DUPLICATE', 'CANNOT_REPRODUCE', 'CLOSED'])
    expect(targets).not.toContain('NEW')
  })

  it('offers reopen (requires reason) from terminal states', () => {
    for (const status of ['DUPLICATE', 'CANNOT_REPRODUCE', 'CLOSED']) {
      const actions = availableStatusActions(status, true)
      expect(actions).toHaveLength(1)
      expect(actions[0]).toMatchObject({ target: 'NEW', needsReason: true })
    }
  })

  it('exposes no manual action for downstream statuses', () => {
    for (const status of ['REQUIREMENT_LINKED', 'PLANNED', 'DEVELOPING', 'TESTING', 'ONLINE']) {
      expect(availableStatusActions(status, true)).toEqual([])
    }
  })

  it('exposes nothing without edit permission', () => {
    expect(availableStatusActions('NEW', false)).toEqual([])
  })
})

describe('feedback API DTO mapping', () => {
  it('createFeedback POSTs the payload to /feedbacks', async () => {
    nextResponse = { status: 200, data: { id: 7, revision: 1 } }
    const payload = {
      title: '标题',
      feedback_type: 'SYSTEM_ISSUE',
      urgency: 'NORMAL',
      description: '描述',
      system_id: null,
      module_id: null,
    }
    const result = await createFeedback(payload)
    expect(result).toMatchObject({ id: 7 })
    expect(lastRequest?.method).toBe('post')
    expect(lastRequest?.url).toBe('/feedbacks')
    expect(JSON.parse(String(lastRequest?.data))).toMatchObject(payload)
  })

  it('changeFeedbackStatus PATCHes /feedbacks/{id}/status with revision + reason', async () => {
    nextResponse = { status: 200, data: { id: 3, status: 'CLOSED', revision: 2 } }
    await changeFeedbackStatus(3, { status: 'CLOSED', revision: 1, reason: '关闭', duplicate_of_id: null })
    expect(lastRequest?.method).toBe('patch')
    expect(lastRequest?.url).toBe('/feedbacks/3/status')
    expect(JSON.parse(String(lastRequest?.data))).toEqual({
      status: 'CLOSED',
      revision: 1,
      reason: '关闭',
      duplicate_of_id: null,
    })
  })

  it('listFeedbacks forwards filter params', async () => {
    nextResponse = { status: 200, data: { items: [], page: 1, page_size: 20, total: 0 } }
    await listFeedbacks({ status: 'NEW', keyword: 'x', page: 2 })
    expect(lastRequest?.params).toMatchObject({ status: 'NEW', keyword: 'x', page: 2 })
  })

  it('surfaces a 409 revision conflict as a rejected promise', async () => {
    nextResponse = { status: 409, data: { code: 40910, message: '冲突' } }
    await expect(
      changeFeedbackStatus(3, { status: 'ACCEPTED', revision: 1 }),
    ).rejects.toMatchObject({ response: { status: 409 } })
  })
})
