import axios, { type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { components } from '@/types/openapi.generated'

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

const { createRequirement, changeRequirementStatus, listRequirementFeedbacks, getOnlineReview, confirmOnlineReview, createOnlineReviewFeedback } = await import(
  '@/api/requirements'
)
const { convertFeedback } = await import('@/api/feedbacks')
const { availableRequirementStatusActions } = await import('@/constants/requirement')

beforeEach(() => {
  lastRequest = null
  nextResponse = { status: 200, data: {} }
  localStorage.clear()
})

describe('availableRequirementStatusActions', () => {
  it('offers DRAFT transitions', () => {
    expect(availableRequirementStatusActions('DRAFT', true).map((a) => a.target)).toEqual([
      'CONFIRMED',
      'CANCELED',
    ])
  })

  it('marks DONE -> DEVELOPING as needing a reason', () => {
    const actions = availableRequirementStatusActions('DONE', true)
    expect(actions).toEqual([{ target: 'DEVELOPING', label: '重新开发', needsReason: true }])
  })

  it('offers nothing for ONLINE/CANCELED or without permission', () => {
    expect(availableRequirementStatusActions('ONLINE', true)).toEqual([])
    expect(availableRequirementStatusActions('CANCELED', true)).toEqual([])
    expect(availableRequirementStatusActions('DRAFT', false)).toEqual([])
  })
})

describe('requirement API DTO mapping', () => {
  it('createRequirement POSTs to /requirements', async () => {
    nextResponse = { status: 200, data: { id: 5, revision: 1 } }
    await createRequirement({
      title: 'T',
      requirement_type: 'FEATURE',
      priority: 'P2',
      description: 'D',
      participants: [{ role: 'CONFIRM', user_id: 2 }],
    })
    expect(lastRequest?.method).toBe('post')
    expect(lastRequest?.url).toBe('/requirements')
  })

  it('changeRequirementStatus PATCHes with status/revision/reason', async () => {
    nextResponse = { status: 200, data: { id: 5, status: 'DEVELOPING' } }
    await changeRequirementStatus(5, 'DEVELOPING', 3, '重新开发')
    expect(lastRequest?.method).toBe('patch')
    expect(lastRequest?.url).toBe('/requirements/5/status')
    expect(JSON.parse(String(lastRequest?.data))).toEqual({
      status: 'DEVELOPING',
      revision: 3,
      reason: '重新开发',
    })
  })

  it('listRequirementFeedbacks GETs the feedbacks path', async () => {
    nextResponse = { status: 200, data: [] }
    await listRequirementFeedbacks(5)
    expect(lastRequest?.method).toBe('get')
    expect(lastRequest?.url).toBe('/requirements/5/feedbacks')
  })

  it('loads the requested page of online review feedbacks', async () => {
    const review = { revision: 3, can_confirm: false, confirmation: null, feedbacks: [], feedback_total: 10 }
    nextResponse = { status: 200, data: review }
    await expect(getOnlineReview(5, 2)).resolves.toEqual(review)
    expect(lastRequest).toMatchObject({ method: 'get', url: '/requirements/5/online-review', params: { page: 2 } })
  })

  it('posts review confirmation with the last read revision and leaves CAS handling to the caller', async () => {
    nextResponse = { status: 409, data: { code: 40910, data: { current_revision: 4 } } }
    const payload = { revision: 3, note: '线上效果符合预期' }
    await expect(confirmOnlineReview(5, payload)).rejects.toMatchObject({ response: { status: 409, data: nextResponse.data } })
    expect(lastRequest).toMatchObject({ method: 'post', url: '/requirements/5/online-review/confirm', skipConflictAlert: true })
    expect(JSON.parse(String(lastRequest?.data))).toEqual(payload)
  })

  it('posts ordinary feedback fields with the requirement revision on the linked feedback path', async () => {
    const feedback = { id: 12, status: 'NEW', main_requirement_id: null }
    nextResponse = { status: 200, data: feedback }
    const payload: components['schemas']['OnlineReviewFeedbackCreate'] = {
      revision: 4, title: '线上反馈', feedback_type: 'SYSTEM_ISSUE', description: '使用后发现的新问题', recipient_ids: [2],
    }
    await expect(createOnlineReviewFeedback(5, payload)).resolves.toEqual(feedback)
    expect(lastRequest).toMatchObject({ method: 'post', url: '/requirements/5/online-review/feedbacks', skipConflictAlert: true })
    expect(JSON.parse(String(lastRequest?.data))).toEqual(payload)
  })

  it('convertFeedback POSTs the CREATE_NEW payload', async () => {
    nextResponse = { status: 200, data: { id: 9, source: 'FEEDBACK' } }
    const req = await convertFeedback(3, {
      type: 'CREATE_NEW',
      revision: 1,
      requirement_title: 'X',
      requirement_type: 'FEATURE',
      description: 'D',
      participants: [{ role: 'CONFIRM', user_id: 2 }],
    })
    expect(req).toMatchObject({ id: 9 })
    expect(lastRequest?.method).toBe('post')
    expect(lastRequest?.url).toBe('/feedbacks/3/convert')
    expect(JSON.parse(String(lastRequest?.data))).toMatchObject({ type: 'CREATE_NEW', revision: 1, participants: [{ role: 'CONFIRM', user_id: 2 }] })
  })

  it('surfaces a 409 duplicate convert as a rejection', async () => {
    nextResponse = { status: 409, data: { code: 40910 } }
    await expect(
      convertFeedback(3, { type: 'CREATE_NEW', revision: 1, requirement_title: 'X', requirement_type: 'FEATURE', description: 'D', participants: [{ role: 'CONFIRM', user_id: 2 }] }),
    ).rejects.toMatchObject({ response: { status: 409 } })
  })
})
