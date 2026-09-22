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

const {
  createFeedback,
  changeFeedbackStatus,
  listFeedbacks,
  createFeedbackComment,
  listFeedbackComments,
  uploadFeedbackAttachment,
} = await import('@/api/feedbacks')
const { availableStatusActions, FEEDBACK_STATUSES } = await import('@/constants/feedback')

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
    for (const status of ['REQUIREMENT_LINKED', 'ONLINE']) {
      expect(availableStatusActions(status, true)).toEqual([])
    }
  })

  it('does not mirror the Requirement or Version R&D lifecycle', () => {
    const statuses = FEEDBACK_STATUSES.map((item) => item.value)
    expect(statuses).not.toContain('PLANNED')
    expect(statuses).not.toContain('DEVELOPING')
    expect(statuses).not.toContain('TESTING')
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

  it('uploadFeedbackAttachment POSTs multipart to the attachments path', async () => {
    nextResponse = { status: 200, data: { file_id: 9, original_name: 'a.txt' } }
    const file = new File([new Blob(['x'])], 'a.txt', { type: 'text/plain' })
    const result = await uploadFeedbackAttachment(5, file)
    expect(result).toMatchObject({ file_id: 9 })
    expect(lastRequest?.method).toBe('post')
    expect(lastRequest?.url).toBe('/feedbacks/5/attachments')
  })

  it('listFeedbackComments GETs the comments path', async () => {
    nextResponse = { status: 200, data: [] }
    await listFeedbackComments(5)
    expect(lastRequest?.method).toBe('get')
    expect(lastRequest?.url).toBe('/feedbacks/5/comments')
  })

  it('createFeedbackComment POSTs {content} to the comments path', async () => {
    nextResponse = { status: 200, data: { id: 1, content: 'hi' } }
    await createFeedbackComment(5, 'hi')
    expect(lastRequest?.method).toBe('post')
    expect(lastRequest?.url).toBe('/feedbacks/5/comments')
    expect(JSON.parse(String(lastRequest?.data))).toEqual({ content: 'hi' })
  })
})
