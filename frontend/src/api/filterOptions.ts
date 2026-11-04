import { api } from './client'
import type { components } from '@/types/openapi.generated'

export type FilterOption = components['schemas']['FilterOption']
export type FilterOptionKind = 'requirement-version' | 'participant' | 'owner'
const paths: Record<FilterOptionKind, string> = {
  'requirement-version': '/requirements/filter-options/versions',
  participant: '/requirements/filter-options/participants',
  owner: '/versions/filter-options/owners',
}

export function listFilterOptions(kind: FilterOptionKind, keyword = '', page = 1, selectedId?: number) {
  return api.get<components['schemas']['FilterOptionPage']>(paths[kind], {
    params: { keyword: keyword.trim().slice(0, 100) || undefined, page, page_size: 20, selected_id: selectedId },
  }).then(response => response.data)
}
