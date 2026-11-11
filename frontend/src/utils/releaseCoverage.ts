import type { BatchTarget, ReleaseBatch } from '@/api/targetReleases'
import { miniProgramSuffixes } from './releaseTargetGroups'

export interface CoverageMember {
  target: BatchTarget
  recordCount: number
}
export interface CoverageGroup {
  key: string
  name: string
  code: string
  kind: 'MINI_PROGRAM' | 'PC_WEB'
  members: CoverageMember[]
}

/** Summarize actual records only; old plans and current directory edits are not publication evidence. */
export function groupReleaseCoverage(batches: ReleaseBatch[]): CoverageGroup[] {
  const latest = new Map<number, { member: CoverageMember; systemId: number }>()
  for (const batch of batches) {
    for (const target of batch.targets) {
      if (!target.completed_at) continue
      const previous = latest.get(target.target_id)
      const newer = !previous || Date.parse(target.completed_at) > Date.parse(previous.member.target.completed_at!) ||
        (target.completed_at === previous.member.target.completed_at && target.id > previous.member.target.id)
      latest.set(target.target_id, {
        member: { target: newer ? target : previous.member.target, recordCount: (previous?.member.recordCount ?? 0) + 1 },
        systemId: batch.system_id,
      })
    }
  }
  const groups = new Map<string, CoverageGroup>()
  for (const { member, systemId } of latest.values()) {
    const target = member.target
    const suffix = miniProgramSuffixes[target.platform as keyof typeof miniProgramSuffixes]
    const code = suffix && target.code.endsWith(suffix) && target.code.length > suffix.length
      ? target.code.slice(0, -suffix.length) : null
    // As with the target directory, never guess brands from matching names.
    const key = code ? JSON.stringify([systemId, code, target.name]) : `target:${target.target_id}`
    const group = groups.get(key) ?? { key, code: code ?? target.code, name: target.name,
      kind: target.platform === 'PC_WEB' ? 'PC_WEB' as const : 'MINI_PROGRAM' as const, members: [] }
    group.members.push(member)
    groups.set(key, group)
  }
  return [...groups.values()]
}
