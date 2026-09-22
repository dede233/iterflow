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

const {
  createVersion,
  changeVersionStatus,
  addVersionRequirement,
  moveVersionRequirement,
  removeVersionRequirement,
  listVersionRequirements,
  publishVersion,
} = await import('@/api/versions')
const {
  availableVersionStatusActions,
  versionRequirementSetFrozen,
} = await import('@/constants/version')

beforeEach(() => {
  lastRequest = null
  nextResponse = { status: 200, data: {} }
  localStorage.clear()
})

describe('version state machine + freeze', () => {
  it('offers PLANNING transitions', () => {
    expect(availableVersionStatusActions('PLANNING', true).map((a) => a.target)).toEqual([
      'DEVELOPING',
      'CANCELED',
    ])
  })

  it('marks READY -> TESTING as needing a reason', () => {
    expect(availableVersionStatusActions('READY', true)).toEqual([
      { target: 'TESTING', label: '退回测试', needsReason: true },
    ])
  })

  it('offers nothing for RELEASED/CANCELED or without permission', () => {
    expect(availableVersionStatusActions('RELEASED', true)).toEqual([])
    expect(availableVersionStatusActions('CANCELED', true)).toEqual([])
    expect(availableVersionStatusActions('PLANNING', false)).toEqual([])
  })

  it('treats READY/RELEASED/CANCELED as frozen', () => {
    expect(versionRequirementSetFrozen('READY')).toBe(true)
    expect(versionRequirementSetFrozen('RELEASED')).toBe(true)
    expect(versionRequirementSetFrozen('CANCELED')).toBe(true)
    expect(versionRequirementSetFrozen('DEVELOPING')).toBe(false)
  })
})

describe('version API DTO mapping', () => {
  it('createVersion POSTs to /versions', async () => {
    nextResponse = { status: 200, data: { id: 1, version_no: 'V1.0.0' } }
    await createVersion({ version_no: 'V1.0.0', name: '首个版本' })
    expect(lastRequest?.method).toBe('post')
    expect(lastRequest?.url).toBe('/versions')
  })

  it('changeVersionStatus PATCHes with status/revision/reason', async () => {
    nextResponse = { status: 200, data: { id: 1, status: 'TESTING' } }
    await changeVersionStatus(1, 'TESTING', 3, '退回测试')
    expect(lastRequest?.url).toBe('/versions/1/status')
    expect(JSON.parse(String(lastRequest?.data))).toEqual({
      status: 'TESTING',
      revision: 3,
      reason: '退回测试',
    })
  })

  it('addVersionRequirement POSTs {requirement_id, revision}', async () => {
    nextResponse = { status: 200, data: { id: 1 } }
    await addVersionRequirement(1, 7, 2)
    expect(lastRequest?.method).toBe('post')
    expect(lastRequest?.url).toBe('/versions/1/requirements')
    expect(JSON.parse(String(lastRequest?.data))).toEqual({ requirement_id: 7, revision: 2 })
  })

  it('moveVersionRequirement POSTs to target /requirements/move', async () => {
    nextResponse = { status: 200, data: { id: 2 } }
    await moveVersionRequirement(2, 7, 3, '迁移原因')
    expect(lastRequest?.url).toBe('/versions/2/requirements/move')
    expect(JSON.parse(String(lastRequest?.data))).toEqual({
      requirement_id: 7,
      revision: 3,
      reason: '迁移原因',
    })
  })

  it('removeVersionRequirement DELETEs with a revision/reason body', async () => {
    nextResponse = { status: 200, data: { id: 1 } }
    await removeVersionRequirement(1, 7, 4, '移出')
    expect(lastRequest?.method).toBe('delete')
    expect(lastRequest?.url).toBe('/versions/1/requirements/7')
    expect(JSON.parse(String(lastRequest?.data))).toEqual({ revision: 4, reason: '移出' })
  })

  it('listVersionRequirements GETs the requirements path', async () => {
    nextResponse = { status: 200, data: { version_id: 1, stats: {}, items: [] } }
    await listVersionRequirements(1)
    expect(lastRequest?.method).toBe('get')
    expect(lastRequest?.url).toBe('/versions/1/requirements')
  })

  it('surfaces a 409 freeze/conflict as a rejection', async () => {
    nextResponse = { status: 409, data: { code: 40930 } }
    await expect(addVersionRequirement(1, 7, 2)).rejects.toMatchObject({ response: { status: 409 } })
  })

  it('publishVersion POSTs release_notes + revision + released_at to /publish', async () => {
    nextResponse = { status: 200, data: { release: { id: 1 }, version_id: 1 } }
    await publishVersion(1, '首次发布', 3)
    expect(lastRequest?.method).toBe('post')
    expect(lastRequest?.url).toBe('/versions/1/publish')
    const sent = JSON.parse(String(lastRequest?.data))
    expect(sent).toMatchObject({ release_notes: '首次发布', revision: 3 })
    expect(typeof sent.released_at).toBe('string')
  })

  it('surfaces a publish 409 (not ready / unfinished requirement) as a rejection', async () => {
    nextResponse = { status: 409, data: { code: 40923 } }
    await expect(publishVersion(1, 'x', 1)).rejects.toMatchObject({ response: { status: 409 } })
  })
})
