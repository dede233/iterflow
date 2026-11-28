import { describe, expect, it } from 'vitest'
import { mailDeliveryReason } from './mailDelivery'

describe('localized mail delivery diagnostics', () => {
  it.each([
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
