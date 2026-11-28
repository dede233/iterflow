import type { components } from '@/types/openapi.generated'

export type MailDeliveryItem = components['schemas']['MailDeliveryItem']
export type MailDeliveryStatus = MailDeliveryItem['status']
export type MailDeliveryKind = MailDeliveryItem['kind']

const statusLabels = {
  PENDING: { label: '待发送', type: 'neutral' },
  SENDING: { label: '发送中', type: 'progress' },
  RETRY: { label: '等待重试', type: 'warning' },
  SENT: { label: '已发送', type: 'success' },
  FAILED: { label: '发送失败', type: 'danger' },
  SKIPPED: { label: '已跳过', type: 'neutral' },
  UNCERTAIN: { label: '结果不确定', type: 'warning' },
} satisfies Record<MailDeliveryStatus, { label: string; type: string }>

export const MAIL_DELIVERY_STATUSES = Object.entries(statusLabels).map(([value, meta]) => ({ value, ...meta }))
export const mailDeliveryStatus = (status: MailDeliveryStatus) => Object.hasOwn(statusLabels, status)
  ? statusLabels[status]
  : { label: '未知状态', type: 'neutral' }

export const MAIL_DELIVERY_KIND_LABELS = {
  EMAIL_VERIFICATION: '邮箱验证（含邀请）',
  COLLABORATION: '业务通知',
} satisfies Record<MailDeliveryKind, string>

export const MAIL_DELIVERY_KINDS = Object.entries(MAIL_DELIVERY_KIND_LABELS).map(([value, label]) => ({ value, label }))

const reasonLabels = {
  ACCESS_REVOKED: '收件人已失去业务访问权限',
  EMAIL_ADDRESS_CHANGED: '当前邮箱与该邮件排队时的地址不同',
  EMAIL_NOT_CONFIGURED: '收件人尚未配置通知邮箱',
  EMAIL_NOT_VERIFIED: '收件人尚未验证当前邮箱',
  EVENT_BEFORE_EMAIL_VERIFICATION: '业务事件发生在当前邮箱验证之前',
  EMAIL_NOTIFICATIONS_OFF: '收件人已关闭业务邮件通知',
  EMAIL_NOT_A_TASK: '收件人仅接收待办邮件，此事件不属于待办',
  OPS_ASSIGNMENT_NO_LONGER_ACTIONABLE: '制作需求已完成或撤回。原分配待办已失效',
  VERIFICATION_EXPIRED_OR_REPLACED: '验证码已失效或已被替换',
  PREFERENCE_OR_EMAIL_CHANGED: '邮件偏好或通知邮箱已变更',
  SMTP_DISABLED: '邮件服务尚未启用',
  NOT_ALLOWLISTED: '收件地址不在允许发送范围内',
  SMTP_OUTCOME_UNCERTAIN: '邮件服务器接受情况未确认',
  SMTP_RECIPIENT_REFUSED: '邮件服务器拒绝该收件人',
  SMTP_CONNECTION_ERROR: '无法连接邮件服务器',
  RETRY_LIMIT: '已达到重试上限',
  // SMTP reply codes from RFC 5321 §4.2.3 and RFC 4954 §6.
  SMTP_421: '邮件服务暂不可用',
  SMTP_450: '收件邮箱暂不可用',
  SMTP_451: '邮件服务器暂时处理失败',
  SMTP_452: '邮件服务器存储空间不足',
  SMTP_454: '邮件服务身份验证暂时失败',
  SMTP_530: '邮件服务要求先验证身份',
  SMTP_535: '邮件服务身份验证失败',
  SMTP_552: '邮件超出服务器存储限制',
}

export function mailDeliveryReason(code: string | null): string {
  if (!code) return '—'
  if (Object.hasOwn(reasonLabels, code)) return reasonLabels[code as keyof typeof reasonLabels]
  if (/^SMTP_4\d{2}$/.test(code)) return '邮件服务器暂时拒绝投递'
  if (/^SMTP_5\d{2}$/.test(code)) return '邮件服务器拒绝投递'
  return '投递原因未知'
}
