import { describe, expect, it } from 'vitest'
import { mailDeliveryReason } from './mailDelivery'

describe('localized mail delivery diagnostics', () => {
  it.each([
    ['EMAIL_ADDRESS_CHANGED', '当前邮箱与该邮件排队时的地址不同'],
    ['EMAIL_NOT_CONFIGURED', '收件人尚未配置通知邮箱'],
    ['EMAIL_NOT_VERIFIED', '收件人尚未验证当前邮箱'],
    ['EVENT_BEFORE_EMAIL_VERIFICATION', '业务事件发生在当前邮箱验证之前'],
    ['EMAIL_NOTIFICATIONS_OFF', '收件人已关闭业务邮件通知'],
    ['EMAIL_NOT_A_TASK', '收件人仅接收待办邮件，此事件不属于待办'],
    ['OPS_ASSIGNMENT_NO_LONGER_ACTIONABLE', '制作需求已完成或撤回。原分配待办已失效'],
    ['VERIFICATION_EXPIRED_OR_REPLACED', '验证码已失效或已被替换'],
    ['PREFERENCE_OR_EMAIL_CHANGED', '邮件偏好或通知邮箱已变更'],
    ['SMTP_421', '邮件服务暂不可用'],
    ['SMTP_450', '收件邮箱暂不可用'],
    ['SMTP_452', '邮件服务器存储空间不足'],
    ['SMTP_454', '邮件服务身份验证暂时失败'],
    ['SMTP_535', '邮件服务身份验证失败'],
    ['SMTP_550', '邮件服务器拒绝投递'],
    ['SMTP_552', '邮件超出服务器存储限制'],
    ['SMTP_499', '邮件服务器暂时拒绝投递'],
    ['SMTP_RECIPIENT_REFUSED', '邮件服务器拒绝该收件人'],
    ['UNKNOWN', '投递原因未知'],
    ['SMTP_550 unrecognized diagnostic', '投递原因未知'],
    [null, '—'],
  ])('maps %s to %s', (code, label) => {
    expect(mailDeliveryReason(code)).toBe(label)
  })
})
