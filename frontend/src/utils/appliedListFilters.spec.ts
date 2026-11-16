import { describe, expect, it } from 'vitest'
import { feedbackFilterChips, versionFilterChips } from './appliedListFilters'

describe('applied list filter chips', () => {
  it('shows only normalized feedback query fields with readable labels', () => {
    expect(feedbackFilterChips({ keyword: '  发票 ', status: 'NEW', feedback_type: 'NEW_FEATURE', urgency: 'URGENT', system_id: '7', module_id: '2', page: '3' }, [{ id: 7, name: '业务系统A' }])).toEqual([
      { key: 'keyword', label: '关键词：发票' },
      { key: 'status', label: '状态：待处理' },
      { key: 'feedback_type', label: '类型：新功能' },
      { key: 'urgency', label: '紧急度：较急' },
      { key: 'system_id', label: '业务系统：业务系统A' },
    ])
  })
  it('does not leak optional system names without dictionary access', () => {
    expect(feedbackFilterChips({ system_id: '7' }, [{ id: 7, name: '系统A' }], false)).toEqual([{ key: 'system_id', label: '业务系统：已指定' }])
  })
  it('rejects invalid values and groups the date range into one removable condition', () => {
    expect(versionFilterChips({ status: 'bad', owner_id: '-2', keyword: ['a'], planned_release_from: '2026-11-01', planned_release_to: '2026-11-12' })).toEqual([
      { key: 'planned_release', label: '计划上线：2026-11-01 至 2026-11-12' },
    ])
    expect(versionFilterChips({ planned_release_from: '2026-11-01' })).toEqual([])
  })
})
