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
  const { status, data } = nextResponse
  const response = { data, status, statusText: 'x', headers: {}, config }
  if (status >= 200 && status < 300) return response
  return Promise.reject({ isAxiosError: true, config, response })
}

const { createRequirement, changeRequirementStatus, listRequirementFeedbacks } = await import(
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

  it('convertFeedback POSTs the CREATE_NEW payload', async () => {
    nextResponse = { status: 200, data: { id: 9, source: 'FEEDBACK' } }
    const req = await convertFeedback(3, {
      type: 'CREATE_NEW',
      revision: 1,
      requirement_title: 'X',
      requirement_type: 'FEATURE',
      description: 'D',
    })
    expect(req).toMatchObject({ id: 9 })
    expect(lastRequest?.method).toBe('post')
    expect(lastRequest?.url).toBe('/feedbacks/3/convert')
    expect(JSON.parse(String(lastRequest?.data))).toMatchObject({ type: 'CREATE_NEW', revision: 1 })
  })

  it('surfaces a 409 duplicate convert as a rejection', async () => {
    nextResponse = { status: 409, data: { code: 40910 } }
    await expect(
      convertFeedback(3, { type: 'CREATE_NEW', revision: 1, requirement_title: 'X', requirement_type: 'FEATURE', description: 'D' }),
    ).rejects.toMatchObject({ response: { status: 409 } })
  })
})
