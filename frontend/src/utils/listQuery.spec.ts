import { describe, expect, it } from 'vitest'
import { detailTarget, listTarget, parseListQuery, sanitizeInternalReturnTarget } from './listQuery'

describe('applied list query contract', () => {
  it.each([
    ['/feedbacks', { status: 'NEW', urgency: 'URGENT', system_id: '003', module_id: '4' }, { status: 'NEW', urgency: 'URGENT', system_id: '3', module_id: '4' }],
    ['/requirements', { priority: 'P1', source: 'DIRECT', owner_id: 7 }, { priority: 'P1', source: 'DIRECT', owner_id: '7' }],
    ['/versions', { status: 'READY', planned_release_from: '2026-10-01', planned_release_to: '2026-10-03' }, { status: 'READY', planned_release_from: '2026-10-01', planned_release_to: '2026-10-03' }],
    ['/releases', { version_id: '8', date_from: '2026-10-01', date_to: '2026-10-03' }, { version_id: '8', date_from: '2026-10-01', date_to: '2026-10-03' }],
    ['/admin/audits', { entity_type: 'REQUIREMENT', entity_id: '7', operator_id: '9', time_from: '2026-10-01T08:00:00+08:00' }, { entity_type: 'REQUIREMENT', entity_id: '7', operator_id: '9', time_from: '2026-10-01T00:00:00.000Z' }],
  ])('%s round trips only approved fields', (path, fields, expected) => {
    const query = { ...fields, page: '2', page_size: '50', keyword: '  query  ', unknown: 'leak', return_to: '//evil' }
    const result = parseListQuery(path, query)
    expect(result).toMatchObject(expected)
    expect(result.page).toBe('2')
    expect(result.unknown).toBeUndefined()
    expect(result.return_to).toBeUndefined()
    expect(sanitizeInternalReturnTarget(listTarget(path, result))).toBe(listTarget(path, result))
  })
  it('rejects invalid IDs, enums, page, arrays, oversized keywords and default fields', () => {
    expect(parseListQuery('/requirements', { page: '-1', page_size: '1000', status: 'invalid', priority: ['P1'], owner_id: '1.5', current_version_id: '9007199254740992', keyword: 'x'.repeat(201) })).toEqual({})
    expect(parseListQuery('/feedbacks', { page: '1', page_size: '20', system_id: '0', module_id: '-3', status: null })).toEqual({})
    expect(parseListQuery('/requirements', { page: '02', keyword: '  a  ' })).toEqual({ page: '2', keyword: 'a' })
  })
  it.each([
    ['/versions', { planned_release_from: '2026-02-30', planned_release_to: 'bad' }],
    ['/versions', { planned_release_from: '2026-10-03', planned_release_to: '2026-10-01' }],
    ['/releases', { date_from: '2026-10-01' }],
    ['/admin/audits', { time_from: '2026-02-30T00:00:00Z', time_to: 'garbage' }],
    ['/admin/audits', { time_from: '2026-10-03T00:00:00Z', time_to: '2026-10-01T00:00:00Z' }],
  ])('invalid dates/ranges are omitted for %s', (path, query) => { expect(parseListQuery(path, query)).toEqual({}) })
  it.each(['https://evil.test', '//evil.test', 'javascript:alert(1)', '%2F%2Fevil.test', '%252F%252Fevil.test', '/requirements?return_to=%2F%2Fevil.test', '/requirements?redirect=%252F%252Fevil.test', '/requirements?source=x', '/requirements?from=x', '/requirements?page=2&page=3', '/requirements#evil', '/requirements\\evil', '/requirements/3', '/login', null, ['a']])('rejects unsafe return target %s', value => { expect(sanitizeInternalReturnTarget(value)).toBeNull() })
  it('retains exact safe list context and strips unknown fields', () => {
    expect(sanitizeInternalReturnTarget('/requirements?page=2&keyword=%E4%B8%AD%E6%96%87&unknown=x')).toBe('/requirements?page=2&keyword=%E4%B8%AD%E6%96%87')
    expect(detailTarget('/requirements/7', '/feedbacks?page=2')).toBe('/requirements/7?return_to=%2Ffeedbacks%3Fpage%3D2')
    expect(detailTarget('/requirements/7', '//evil.test')).toBe('/requirements/7')
  })
})
