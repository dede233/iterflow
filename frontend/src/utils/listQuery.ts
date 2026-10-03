import type { LocationQuery } from 'vue-router'
import { FEEDBACK_STATUSES, FEEDBACK_TYPES, FEEDBACK_URGENCIES } from '@/constants/feedback'
import { REQUIREMENT_PRIORITIES, REQUIREMENT_STATUSES } from '@/constants/requirement'
import { VERSION_STATUSES } from '@/constants/version'
import { auditActionOptions, auditEntityOptions } from '@/utils/auditLabels'

type Rule = (value: string) => string | undefined
const positive: Rule = value => /^\d+$/.test(value) && Number.isSafeInteger(Number(value)) && Number(value) > 0 ? String(Number(value)) : undefined
const enumeration = (values: readonly { value: string }[]): Rule => value => values.some(option => option.value === value) ? value : undefined
const keyword: Rule = value => value.trim() && value.trim().length <= 200 ? value.trim() : undefined
const day: Rule = value => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return undefined
  const date = new Date(`${value}T00:00:00Z`)
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value ? value : undefined
}
const instant: Rule = value => {
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(?:Z|[+-](\d{2}):(\d{2}))$/.exec(value)
  if (!match || !day(match[1]!) || Number(match[2]) > 23 || Number(match[3]) > 59 || Number(match[4]) > 59 || Number(match[5] ?? 0) > 23 || Number(match[6] ?? 0) > 59) return undefined
  return Number.isFinite(Date.parse(value)) ? new Date(value).toISOString() : undefined
}
const size: Rule = value => positive(value) && Number(value) <= 100 && Number(value) !== 20 ? String(Number(value)) : undefined
const page: Rule = value => positive(value) && Number(value) !== 1 ? String(Number(value)) : undefined
const schemas: Record<string, Record<string, Rule>> = {
  '/feedbacks': { page, page_size: size, keyword, status: enumeration(FEEDBACK_STATUSES), feedback_type: enumeration(FEEDBACK_TYPES), urgency: enumeration(FEEDBACK_URGENCIES), system_id: positive, module_id: positive },
  '/requirements': { page, page_size: size, keyword, status: enumeration(REQUIREMENT_STATUSES), priority: enumeration(REQUIREMENT_PRIORITIES), source: enumeration([{ value: 'DIRECT' }, { value: 'FEEDBACK' }]), current_version_id: positive, owner_id: positive },
  '/versions': { page, page_size: size, keyword, status: enumeration(VERSION_STATUSES), owner_id: positive, planned_release_from: day, planned_release_to: day },
  '/releases': { page, page_size: size, version_id: positive, date_from: day, date_to: day },
  '/admin/audits': { page, size, entity_type: enumeration(auditEntityOptions), entity_id: positive, action: enumeration(auditActionOptions), operator_id: positive, time_from: instant, time_to: instant },
}

/** Only applied, explicitly typed list fields may enter a URL. Arrays are invalid. */
export function parseListQuery(path: string, query: LocationQuery | Record<string, unknown>): Record<string, string> {
  const result: Record<string, string> = {}
  for (const [key, rule] of Object.entries(schemas[path] ?? {})) {
    const raw = query[key]
    if (typeof raw !== 'string' && typeof raw !== 'number') continue
    const valid = rule(String(raw))
    if (valid !== undefined) result[key] = valid
  }
  for (const [from, to] of [['planned_release_from', 'planned_release_to'], ['date_from', 'date_to'], ['time_from', 'time_to']]) {
    if (!!result[from!] !== !!result[to!] || (result[from!] && result[to!] && result[from!]! > result[to!]!)) { delete result[from!]; delete result[to!] }
  }
  // UI range pickers require both endpoints; never apply an invisible half-range.
  return result
}
export const serializeListQuery = parseListQuery
export function listTarget(path: string, query: Record<string, unknown>): string {
  const search = new URLSearchParams(parseListQuery(path, query)).toString()
  return path + (search ? `?${search}` : '')
}

/** Never decode the path recursively or accept nested return/redirect parameters. */
export function sanitizeInternalReturnTarget(value: unknown): string | null {
  if (typeof value !== 'string' || value.length > 4096 || /[\\#\u0000-\u001f\u007f]/.test(value)) return null
  const [path, ...tail] = value.split('?')
  if (!path || !Object.hasOwn(schemas, path) || tail.length > 1) return null
  const params = new URLSearchParams(tail[0] ?? '')
  const query: Record<string, string> = {}
  for (const key of params.keys()) {
    if ((['return_to', 'redirect', 'from'].includes(key) || (key === 'source' && (path !== '/requirements' || !['DIRECT', 'FEEDBACK'].includes(params.get(key)!)))) || params.getAll(key).length !== 1) return null
    query[key] = params.get(key)!
  }
  return listTarget(path, query)
}
export function detailTarget(path: string, returnTo: unknown): string {
  const safe = sanitizeInternalReturnTarget(returnTo)
  return safe ? `${path}?return_to=${encodeURIComponent(safe)}` : path
}
