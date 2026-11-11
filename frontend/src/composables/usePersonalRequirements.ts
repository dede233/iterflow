import { onScopeDispose, reactive, watch } from 'vue'
import { listRequirements } from '@/api/requirements'
import type { Requirement, RequirementListParams } from '@/types/domain'

export const PERSONAL_REQUIREMENT_GROUPS = [
  { key: 'confirm', title: '内容确认', linkLabel: '查看待我确认的需求', status: 'DRAFT', role: 'CONFIRM' },
  { key: 'develop', title: '开发准备', linkLabel: '查看待我开发的需求', status: 'CONFIRMED', role: 'DEVELOP' },
  { key: 'accept', title: '交付验收', linkLabel: '查看待我验收的需求', status: 'TESTING', role: 'ACCEPT' },
] as const

export type PersonalRequirementGroup = {
  key: string; title: string; linkLabel: string; status: RequirementListParams['status']; role: RequirementListParams['participant_role']
  items: Requirement[]; total: number; loading: boolean; failed: boolean
}

/** Three bounded, server-scoped lists. No global overview count is used as a personal count. */
export function usePersonalRequirements(identity: () => readonly [number | undefined, boolean, string]) {
  const groups = reactive<PersonalRequirementGroup[]>(PERSONAL_REQUIREMENT_GROUPS.map(group => ({ ...group, items: [], total: 0, loading: false, failed: false })))
  let generation = 0
  let disposed = false
  const requests = new Map<string, number>()

  async function load(group: PersonalRequirementGroup, current = generation) {
    const [viewerId, allowed] = identity()
    if (disposed || !allowed || !viewerId || !Number.isSafeInteger(viewerId) || viewerId < 1) return
    const request = (requests.get(group.key) ?? 0) + 1
    requests.set(group.key, request)
    group.loading = true
    group.failed = false
    group.items = []
    group.total = 0
    const active = () => !disposed && current === generation && requests.get(group.key) === request
    try {
      const result = await listRequirements({ page: 1, page_size: 3, status: group.status, participant_id: viewerId, participant_role: group.role })
      if (!active()) return
      group.items = result.items
      group.total = result.total
    } catch {
      if (active()) group.failed = true
    } finally {
      if (active()) group.loading = false
    }
  }

  watch(identity, ([viewerId, allowed]) => {
    generation++
    for (const group of groups) {
      Object.assign(group, { items: [], total: 0, loading: false, failed: false })
      if (allowed && viewerId && Number.isSafeInteger(viewerId) && viewerId > 0) void load(group)
    }
  }, { immediate: true, flush: 'sync' })
  onScopeDispose(() => { disposed = true; generation++; for (const group of groups) group.items = [] })
  return { groups, retry: (key: string) => { const group = groups.find(item => item.key === key); if (group) void load(group) } }
}
