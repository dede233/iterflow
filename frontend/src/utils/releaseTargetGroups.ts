import type { ReleaseTarget } from '@/api/targetReleases'

export const miniProgramSuffixes = { WECHAT_MINI_PROGRAM: '_WX', ALIPAY_MINI_PROGRAM: '_ALIPAY' } as const
export type MiniProgramPlatform = keyof typeof miniProgramSuffixes
export interface ReleaseTargetGroup {
  key: string
  code: string
  name: string
  kind: 'MINI_PROGRAM' | 'PC_WEB'
  members: ReleaseTarget[]
}

export function miniProgramCode(target: ReleaseTarget) {
  const suffix = miniProgramSuffixes[target.platform as MiniProgramPlatform]
  return suffix && target.code.endsWith(suffix) && target.code.length > suffix.length
    ? target.code.slice(0, -suffix.length) : null
}

export function groupReleaseTargets(targets: ReleaseTarget[]): ReleaseTargetGroup[] {
  const groups = new Map<string, ReleaseTargetGroup>()
  for (const target of targets) {
    const prefix = miniProgramCode(target)
    // Never infer a legacy brand from its name alone or mix business systems.
    const key = prefix === null ? `target:${target.id}` : JSON.stringify([target.system_id, prefix, target.name])
    const group = groups.get(key) ?? {
      key, code: prefix ?? target.code, name: target.name,
      kind: target.platform === 'PC_WEB' ? 'PC_WEB' : 'MINI_PROGRAM', members: [],
    }
    group.members.push(target)
    groups.set(key, group)
  }
  return [...groups.values()]
}
