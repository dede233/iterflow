import { describe, expect, it } from 'vitest'
import type { BatchTarget, ReleaseBatch } from '@/api/targetReleases'
import { groupReleaseCoverage } from './releaseCoverage'

const row = (id: number, targetId: number, platform: BatchTarget['platform'], code: string, completedAt: string | null, name = '品牌 A') =>
  ({ id, target_id: targetId, platform, code, completed_at: completedAt, name } as BatchTarget)
const batch = (id: number, targets: BatchTarget[], systemId = 1) => ({ id, system_id: systemId, targets } as ReleaseBatch)
describe('brand coverage from historical publication evidence', () => {
  it('joins platform snapshots by explicit brand code and keeps separate actual times', () => {
    const groups = groupReleaseCoverage([
      batch(1, [row(1, 1, 'WECHAT_MINI_PROGRAM', 'A_WX', '2026-11-01T10:00:00Z')]),
      batch(2, [row(2, 2, 'ALIPAY_MINI_PROGRAM', 'A_ALIPAY', '2026-11-03T10:00:00Z')]),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].members.map(m => m.target.completed_at)).toEqual(['2026-11-01T10:00:00Z', '2026-11-03T10:00:00Z'])
  })
  it('never counts planned-only targets or guesses brands from names', () => {
    const groups = groupReleaseCoverage([batch(1, [
      row(1, 1, 'WECHAT_MINI_PROGRAM', 'A', null),
      row(2, 2, 'ALIPAY_MINI_PROGRAM', 'B', '2026-11-01T10:00:00Z'),
      row(3, 3, 'PC_WEB', 'A_WX', '2026-11-02T10:00:00Z'),
      row(4, 4, 'WECHAT_MINI_PROGRAM', 'B_WX', '2026-11-02T10:00:00Z'),
    ])])
    expect(groups).toHaveLength(3)
    expect(groups.flatMap(g => g.members).map(m => m.target.target_id)).toEqual([2, 3, 4])
    expect(groups[1].kind).toBe('PC_WEB')
  })
  it('chooses most recent actual publication independently of input or registration order', () => {
    const earlier = row(40, 1, 'WECHAT_MINI_PROGRAM', 'A_WX', '2026-11-01T10:00:00Z')
    const newer = row(2, 1, 'WECHAT_MINI_PROGRAM', 'A_WX', '2026-11-02T10:00:00Z')
    for (const targets of [[earlier, newer], [newer, earlier]]) {
      const result = groupReleaseCoverage([batch(1, targets)])
      expect(result[0].members[0]).toEqual({ target: newer, recordCount: 2 })
    }
  })
  it('does not combine cross-system targets or differently named historical snapshots', () => {
    const groups = groupReleaseCoverage([
      batch(1, [row(1, 1, 'WECHAT_MINI_PROGRAM', 'A_WX', '2026-11-01T10:00:00Z')]),
      batch(2, [row(2, 2, 'ALIPAY_MINI_PROGRAM', 'A_ALIPAY', '2026-11-03T10:00:00Z')], 2),
      batch(3, [row(3, 3, 'ALIPAY_MINI_PROGRAM', 'A_ALIPAY', '2026-11-03T10:00:00Z', '另一个品牌')]),
    ])
    expect(groups).toHaveLength(3)
  })
})
