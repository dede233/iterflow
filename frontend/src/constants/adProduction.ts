import type { components } from '@/types/openapi.generated'

export type AdProductionStatus = components['schemas']['AdProductionOut']['status']
export type AdProductionKind = components['schemas']['AdProductionKind']

export const AD_PRODUCTION_LABELS = {
  MATERIAL: { name: '物料制作' },
  MERCHANT_AD: { name: '商家广告' },
} as const satisfies Record<AdProductionKind, { name: string }>

export const AD_PRODUCTION_PERMISSIONS = {
  MATERIAL: { view: 'ops.ad_production.view', create: 'ops.ad_production.create', edit: 'ops.ad_production.edit' },
  MERCHANT_AD: { view: 'ops.merchant_ad.view', create: 'ops.merchant_ad.create', edit: 'ops.merchant_ad.edit' },
} as const satisfies Record<AdProductionKind, { view: string; create: string; edit: string }>

export const AD_PRODUCTION_PUBLISHER_LABEL = '需求发布人'

export const AD_PRODUCTION_STATUS_DISPLAY = {
  NOT_STARTED: { label: '未开始', tone: 'neutral' },
  IN_PROGRESS: { label: '进行中', tone: 'progress' },
  SHIPPING: { label: '邮寄中', tone: 'warning' },
  COMPLETED: { label: '已完成', tone: 'success' },
  WITHDRAWN: { label: '已撤回', tone: 'neutral' },
} as const satisfies Record<AdProductionStatus, { label: string; tone: string }>

export const AD_PRODUCTION_STATUSES = (Object.keys(AD_PRODUCTION_STATUS_DISPLAY) as AdProductionStatus[])
  .map(value => ({ value, label: AD_PRODUCTION_STATUS_DISPLAY[value].label }))

const MERCHANT_AD_STATUS_LABELS: Partial<Record<AdProductionStatus, string>> = {
  NOT_STARTED: '未处理',
  IN_PROGRESS: '处理中',
  COMPLETED: '已处理',
}

export const MERCHANT_AD_STATUSES = AD_PRODUCTION_STATUSES
  .filter(({ value }) => value !== 'SHIPPING')
  .map(({ value, label }) => ({ value, label: MERCHANT_AD_STATUS_LABELS[value] ?? label }))

export function adProductionStatusDisplay(kind: AdProductionKind, status: AdProductionStatus): { label: string; tone: string } {
  const display = AD_PRODUCTION_STATUS_DISPLAY[status]
  return { label: (kind === 'MERCHANT_AD' && MERCHANT_AD_STATUS_LABELS[status]) || display.label, tone: display.tone }
}

export const AD_PRODUCTION_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
