import { expect, it } from 'vitest'
import type { Requirement } from '@/types/domain'
import { filterVersionWorklist, visibleWorklistStats } from './versionWorklist'
const items = [
  { id: 1, requirement_no: 'REQ-1', title: '修复中文 Search', status: 'DEVELOPING', priority: 'P0' },
  { id: 2, requirement_no: 'REQ-2', title: 'Search done', status: 'DONE', priority: 'P1' },
  { id: 3, requirement_no: 'REQ-3', title: 'Other', status: 'ONLINE', priority: 'P0' },
] as Requirement[]
it('intersects keyword/status/priority without modifying visible input', () => {
  expect(filterVersionWorklist(items, { keyword: ' search ', status: '', priority: '' }).map(x => x.id)).toEqual([1, 2])
  expect(filterVersionWorklist(items, { keyword: 'REQ-', status: 'DEVELOPING', priority: 'P0' }).map(x => x.id)).toEqual([1])
  expect(filterVersionWorklist(items, { keyword: 'no result', status: '', priority: '' })).toEqual([])
  expect(filterVersionWorklist(items, { keyword: '', status: '', priority: '' })).toEqual(items)
  expect(items).toHaveLength(3)
})
it('stats represent only passed visible subset, never infer publish readiness', () => {
  expect(visibleWorklistStats(items)).toEqual({ total: 3, pending: 1, byStatus: { DEVELOPING: 1, DONE: 1, ONLINE: 1 } })
  expect(visibleWorklistStats(items.slice(1))).toEqual({ total: 2, pending: 0, byStatus: { DONE: 1, ONLINE: 1 } })
  expect(visibleWorklistStats([])).toEqual({ total: 0, pending: 0, byStatus: {} })
})
