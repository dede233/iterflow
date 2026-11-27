import type { AdProduction } from '@/api/adProductions'
import { AD_PRODUCTION_LABELS } from '@/constants/adProduction'
import { richTextPlainText } from '@/utils/richText'

export function adProductionText(record: AdProduction): string {
  return record.content_format === 'HTML' ? richTextPlainText(record.content) : record.content
}

export function adProductionTitle(record: AdProduction): string {
  if (record.title) return record.title
  const excerpt = Array.from(adProductionText(record).replace(/\s+/g, ' ').trim())
  if (!excerpt.length) return `${AD_PRODUCTION_LABELS[record.kind ?? 'MATERIAL'].name}需求`
  return excerpt.length > 80 ? `${excerpt.slice(0, 80).join('')}…` : excerpt.join('')
}

export function publisherName(record: AdProduction): string {
  return record.publisher_display_name || `用户 #${record.created_by}`
}

export function designerName(record: AdProduction, field: 'receiver_id' | 'completed_by_id'): string {
  const id = record[field]
  const name = field === 'receiver_id' ? record.receiver_display_name : record.completed_by_display_name
  return name || (id == null ? '—' : `用户 #${id}`)
}
