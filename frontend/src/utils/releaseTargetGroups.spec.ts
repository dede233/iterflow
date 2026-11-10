import { describe, expect, it } from 'vitest'
import type { ReleaseTarget } from '@/api/targetReleases'
import { groupReleaseTargets } from './releaseTargetGroups'
const target = (id: number, code: string, platform: ReleaseTarget['platform'], system_id = 1, name = '品牌 A') => ({ id, code, platform, system_id, name } as ReleaseTarget)
describe('platforms grouped under their explicit brand code', () => {
  it('combines configured WeChat and Alipay, independently of order', () => {
    const groups = groupReleaseTargets([target(1, 'A_ALIPAY', 'ALIPAY_MINI_PROGRAM'), target(2, 'A_WX', 'WECHAT_MINI_PROGRAM')])
    expect(groups).toHaveLength(1); expect(groups[0].code).toBe('A'); expect(groups[0].members.map(t => t.id)).toEqual([1, 2])
  })
  it('does not infer shared brands from names, cross-system codes, or mismatched platforms', () => {
    const rows = [target(1, 'A', 'WECHAT_MINI_PROGRAM'), target(2, 'B', 'ALIPAY_MINI_PROGRAM'), target(3, 'A_WX', 'WECHAT_MINI_PROGRAM'), target(4, 'A_ALIPAY', 'ALIPAY_MINI_PROGRAM', 2), target(5, 'A_ALIPAY', 'PC_WEB'), target(6, 'A_ALIPAY', 'ALIPAY_MINI_PROGRAM', 1, 'other brand')]
    expect(groupReleaseTargets(rows)).toHaveLength(6)
  })
})
