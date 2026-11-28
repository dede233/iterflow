import { expect, test, type Page, type Route } from '@playwright/test'
import { mockCollaboration } from './collaboration-fixture'

const monitorPath = '/admin/mail-delivery-monitor'
const deliveryUrl = `/api/v1${monitorPath}`
const profile = {
  id: 1, username: 'admin', display_name: '系统管理员', email: null,
  status: 'ACTIVE', revision: 1, data_scope: 'ALL', role_ids: [1],
  must_change_password: false, permission_codes: ['*'], can_view_api_docs: true,
  can_view_mail_deliveries: true,
}
const people = [
  { user_id: 417, display_name: '严小雨', username: 'yan.research' },
  { user_id: 418, display_name: '严小雨', username: 'yan.operations' },
  { user_id: 419, display_name: '李明', username: 'li' },
]
const date = '2026-11-26T08:00:00Z'
const eventDate = '2026-11-26T07:55:00Z'
const maskedRecipient = 'y***@example.test'
const sentDeliveryId = 'verification-delivery'
const sentResendToken = 'verification-resend-token'
const deliveries = [
  { id: '61b66468-59ce-4b13-ba25-af97b9a5580e', ...people[0]!, kind: 'COLLABORATION', status: 'FAILED', attempts: 3, error_code: 'SMTP_550', created_at: date, next_attempt_at: null, resend_token: 'failed-resend-token', resend_block_reason: null },
  { id: sentDeliveryId, ...people[1]!, kind: 'EMAIL_VERIFICATION', status: 'SENT', attempts: 1, error_code: null, created_at: date, next_attempt_at: null, resend_token: sentResendToken, resend_block_reason: null },
  { id: 'verification-for-yan', ...people[0]!, kind: 'EMAIL_VERIFICATION', status: 'FAILED', attempts: 4, error_code: 'UNKNOWN', created_at: date, next_attempt_at: null, resend_token: null, resend_block_reason: '收件人已完成邮箱验证。' },
  { id: 'business-delivery', ...people[2]!, kind: 'COLLABORATION', status: 'RETRY', attempts: 1, error_code: 'SMTP_CONNECTION_ERROR', created_at: date, next_attempt_at: date, resend_token: null, resend_block_reason: '该邮件正在等待重试。' },
]

function deliveryDetail(row: (typeof deliveries)[number]) {
  const { id, username, display_name, kind, status, attempts, error_code, created_at, next_attempt_at } = row
  return {
    id, username, display_name, kind, status, attempts, error_code, created_at, next_attempt_at,
    masked_email: id === 'business-delivery' ? null : maskedRecipient,
    event_label: kind === 'EMAIL_VERIFICATION' ? '验证通知邮箱' : '需求已提交验收',
    event_created_at: eventDate,
  }
}

async function mockMail(page: Page, user = profile, { canResend = false, resendConflict = false } = {}) {
  const reads: URLSearchParams[] = []
  const lookups: URLSearchParams[] = []
  const retries: unknown[] = []
  const resends: { id: string; payload: unknown }[] = []
  const rows = deliveries.map(item => canResend ? { ...item } : { ...item, resend_token: null, resend_block_reason: null })
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'mail-test-access')
    localStorage.setItem('iterflow.refresh_token', 'mail-test-refresh')
  })
  await page.route('**/api/v1/**', async route => {
    if (await mockCollaboration(route)) return
    const { pathname, searchParams } = new URL(route.request().url())
    if (pathname === '/api/v1/auth/me') return route.fulfill({ json: user })
    if (pathname === '/api/v1/notifications/unread-count') return route.fulfill({ json: { unread_count: 0 } })
    if (pathname === `${deliveryUrl}/recipients`) {
      lookups.push(searchParams)
      const keyword = searchParams.get('keyword') || ''
      const selected = searchParams.get('selected_id')
      const items = people.filter(person => (!selected || String(person.user_id) === selected) && `${person.display_name} ${person.username}`.includes(keyword))
      return route.fulfill({ json: { items, total: items.length, page: 1, page_size: 20 } })
    }
    if (pathname === deliveryUrl) {
      reads.push(searchParams)
      const kind = searchParams.get('kind')
      const status = searchParams.get('status')
      const recipient = searchParams.get('user_id')
      const pageNumber = Number(searchParams.get('page') || 1)
      const items = rows.filter(item => (!kind || item.kind === kind) && (!status || item.status === status) && (!recipient || String(item.user_id) === recipient))
      if (pageNumber === 2) items.reverse()
      return route.fulfill({ json: { items, total: kind || status || recipient ? items.length : 21, page: pageNumber, page_size: 20, can_resend_mail_deliveries: canResend } })
    }
    const viewed = rows.find(row => pathname === `${deliveryUrl}/${row.id}`)
    if (viewed) {
      expect(route.request().method()).toBe('GET')
      return route.fulfill({ json: deliveryDetail(viewed) })
    }
    if (pathname === `${deliveryUrl}/${sentDeliveryId}/resend`) {
      expect(route.request().method()).toBe('POST')
      resends.push({ id: sentDeliveryId, payload: route.request().postDataJSON() })
      const row = rows.find(item => item.id === sentDeliveryId)!
      row.resend_token = null
      if (resendConflict) {
        row.resend_block_reason = '收件人已完成邮箱验证。'
        return route.fulfill({ status: 409, json: { message: '收件人已完成邮箱验证。' } })
      }
      row.status = 'PENDING'
      row.attempts = 0
      row.error_code = null
      row.resend_block_reason = '该邮件正在排队发送。'
      return route.fulfill({ status: 204 })
    }
    if (pathname === `/api/v1/admin/mail-deliveries/${rows[0]!.id}/retry`) {
      expect(route.request().method()).toBe('POST')
      retries.push(route.request().postDataJSON())
      rows[0]!.status = 'PENDING'
      rows[0]!.attempts = 0
      rows[0]!.error_code = null
      return route.fulfill({ status: 204 })
    }
    return route.fulfill({ status: 404, json: {} })
  })
  return { reads, lookups, retries, resends }
}

for (const width of [1440, 375]) {
  test(`mail records navigation, filters and retry work at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const { reads, lookups, retries } = await mockMail(page)
    await page.goto('/#/profile')
    await expect(page.getByRole('heading', { name: '个人中心' })).toBeVisible()
    await expect(page.getByRole('main').getByText('邮件记录', { exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '查看邮件投递记录' })).toHaveCount(0)
    expect(reads).toHaveLength(0)

    if (width === 375) {
      await page.getByRole('button', { name: '工作台', exact: true }).click()
      await page.getByRole('menuitem', { name: '邮件记录', exact: true }).click()
    } else {
      const group = page.locator('.nav-group').filter({ has: page.getByText('工作台', { exact: true }) })
      await group.getByRole('link', { name: '邮件记录', exact: true }).click()
    }
    const main = page.getByRole('main')
    await expect(main.getByRole('heading', { name: '邮件记录', exact: true })).toBeVisible()
    await expect(main.getByText(/SMTP 服务器已接受邮件/)).toBeVisible()
    await expect(main.getByText('邮件服务器拒绝投递', { exact: true })).toBeVisible()
    await expect(main.getByText('投递原因未知', { exact: true })).toBeVisible()
    await expect(main.getByText('SMTP_550', { exact: true })).toHaveCount(0)
    await expect(main.getByText('用户 #417', { exact: true })).toHaveCount(0)
    await expect(main.getByRole('radiogroup', { name: '邮件类型' })).toHaveCount(0)
    expect(await main.locator(width === 375 ? '.delivery-cards' : '.delivery-table').count()).toBe(1)
    await expect(main.getByText('严小雨', { exact: true }).first()).toBeVisible()
    await expect(main.getByText('yan.operations', { exact: true })).toBeVisible()
    await page.screenshot({ path: info.outputPath(`mail-records-${width}.png`), animations: 'disabled' })

    await main.getByRole('button', { name: '下一页', exact: true }).click()
    await expect(main.getByText('第 2 / 2 页')).toBeVisible()
    await expect.poll(() => reads.at(-1)?.get('page')).toBe('2')
    const pageTwoReadCount = reads.length

    if (width === 375) await main.getByRole('button', { name: '筛选', exact: true }).click()
    const filters = width === 375 ? page.getByRole('dialog', { name: '筛选邮件记录' }) : main.locator('.mail-record-filters')
    if (width === 375) {
      const applyButton = filters.getByRole('button', { name: '查询', exact: true })
      await expect(applyButton).toBeVisible()
      expect((await applyButton.boundingBox())?.height).toBeGreaterThanOrEqual(44)
    }
    const kind = filters.getByRole('combobox', { name: '邮件类型', exact: true })
    await kind.press('ArrowDown')
    await expect(page.getByRole('option', { name: '全部类型', exact: true })).toBeVisible()
    await expect(page.getByRole('option', { name: '邮箱验证（含邀请）', exact: true })).toBeVisible()
    await page.getByRole('option', { name: '业务通知', exact: true }).click()
    await filters.getByRole('combobox', { name: '投递状态', exact: true }).press('ArrowDown')
    await page.getByRole('option', { name: '发送失败', exact: true }).click()
    const recipient = filters.getByRole('combobox', { name: '收件人', exact: true })
    await recipient.press('ArrowDown')
    await recipient.fill('no-matching-recipient')
    await expect(page.getByText('没有匹配的邮件收件人，请检查姓名或登录账号')).toBeVisible()
    await recipient.fill('严小雨')
    await expect.poll(() => lookups.at(-1)?.get('keyword')).toBe('严小雨')
    await expect(page.getByRole('option', { name: /严小雨.*yan\.operations/ })).toBeVisible()
    await page.screenshot({ path: info.outputPath(`mail-recipient-filter-${width}.png`), animations: 'disabled' })
    await page.getByRole('option', { name: /严小雨.*yan\.research/ }).click()
    await expect(page).toHaveURL(/\?page=2$/)
    expect(reads).toHaveLength(pageTwoReadCount)
    await filters.getByRole('button', { name: '查询', exact: true }).click()
    const combinedQuery = { page: '1', page_size: '20', kind: 'COLLABORATION', status: 'FAILED', user_id: '417' }
    await expect.poll(() => Object.fromEntries(reads.at(-1) ?? [])).toEqual(combinedQuery)
    await expect(main.getByRole('navigation', { name: '投递记录分页' })).toHaveCount(0)
    await expect(main.getByText('共 1 条记录', { exact: true })).toBeVisible()
    await expect(main.getByText('yan.research', { exact: true })).toBeVisible()
    await expect(main.getByText('yan.operations', { exact: true })).toHaveCount(0)
    await expect(main.getByRole('button', { name: '重发邮件', exact: true })).toHaveCount(0)
    await expect(main.getByRole('button', { name: '重新投递', exact: true })).toHaveCount(1)
    await main.getByRole('button', { name: '重新投递', exact: true }).click()
    await expect(main.getByText('当前条件下暂无投递记录')).toBeVisible()
    expect(retries).toEqual([{ attempts: 3 }])

    if (width === 375) await main.getByRole('button', { name: '筛选 (3)', exact: true }).click()
    await filters.getByRole('button', { name: '重置', exact: true }).click()
    await expect.poll(() => Object.fromEntries(reads.at(-1) ?? [])).toEqual({ page: '1', page_size: '20' })
    await expect(page).toHaveURL(/#\/admin\/mail-delivery-monitor$/)
    await expect(main.getByText('共 21 条记录', { exact: true })).toBeVisible()
    if (width === 375) await main.getByRole('button', { name: '筛选', exact: true }).click()
    await expect(filters.getByText('全部类型', { exact: true })).toBeVisible()
    await expect(filters.getByText('全部状态', { exact: true })).toBeVisible()
    await expect(filters.getByText('搜索姓名或登录账号', { exact: true })).toBeVisible()

    await page.goBack()
    await expect.poll(() => Object.fromEntries(reads.at(-1) ?? [])).toEqual(combinedQuery)
    await expect(filters.getByText('业务通知', { exact: true })).toBeVisible()
    await expect(filters.getByText('发送失败', { exact: true })).toBeVisible()
    await expect(filters.getByText('严小雨（yan.research）', { exact: true })).toBeVisible()
    await page.goForward()
    await expect.poll(() => Object.fromEntries(reads.at(-1) ?? [])).toEqual({ page: '1', page_size: '20' })
    await expect(filters.getByText('全部类型', { exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
  })

  test(`built-in administrator confirms mail resend at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const { reads, retries, resends } = await mockMail(page, profile, { canResend: true })
    await page.goto(`/#${monitorPath}`)
    const main = page.getByRole('main')
    const row = (name: string) => main.locator(width === 375 ? '.delivery-card' : 'tbody tr').filter({ hasText: name })
    const blocked = row('李明')
    await expect(blocked.getByRole('button', { name: '重发邮件', exact: true })).toBeDisabled()
    await expect(blocked.getByText('该邮件正在等待重试。')).toBeVisible()
    await expect(main.getByRole('button', { name: '重新投递', exact: true })).toHaveCount(0)
    await page.screenshot({ path: info.outputPath(`mail-resend-actions-${width}.png`), animations: 'disabled' })
    if (width === 1440) {
      await page.setViewportSize({ width: 1200, height: 900 })
      const table = main.locator('.delivery-table')
      const scrollArea = table.locator('.el-scrollbar__wrap')
      const resendButton = page.getByRole('button', { name: '重发邮件', exact: true })
      const actionCell = row('yan.operations').getByRole('cell').filter({ has: resendButton })
      await expect.poll(() => scrollArea.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true)
      await expect.poll(() => actionCell.evaluate(element => {
        const tableBounds = element.closest('.delivery-table')!.getBoundingClientRect()
        return element.getBoundingClientRect().right - tableBounds.right
      })).toBeLessThanOrEqual(1)
      await expect(actionCell.getByRole('button', { name: '重发邮件', exact: true })).toBeInViewport({ ratio: 1 })
      await page.screenshot({ path: info.outputPath('mail-resend-actions-1200.png'), animations: 'disabled' })
      await page.setViewportSize({ width, height: 900 })
    } else {
      await blocked.scrollIntoViewIfNeeded()
      await expect(blocked.getByText('该邮件正在等待重试。')).toBeInViewport()
      await blocked.screenshot({ path: info.outputPath('mail-resend-disabled-375.png'), animations: 'disabled' })
    }

    await page.goto(`/#${monitorPath}?kind=EMAIL_VERIFICATION&status=SENT&user_id=418`)
    const resend = row('yan.operations').getByRole('button', { name: '重发邮件', exact: true })
    if (width === 375) expect((await resend.boundingBox())?.height).toBeGreaterThanOrEqual(44)
    await resend.click()
    const dialog = page.getByRole('dialog', { name: '确认重发邮件' })
    await expect(dialog.getByText('严小雨（yan.operations）', { exact: true })).toBeVisible()
    await expect(dialog.getByText('邮箱验证（含邀请）', { exact: true })).toBeVisible()
    expect(resends).toHaveLength(0)
    await page.screenshot({ path: info.outputPath(`mail-resend-confirm-${width}.png`), animations: 'disabled' })
    if (width === 375) await dialog.getByRole('button', { name: '取消', exact: true }).click()
    else await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    expect(resends).toHaveLength(0)

    await resend.click()
    await dialog.getByRole('button', { name: '确认重发', exact: true }).click()
    await expect(dialog).toBeHidden()
    await expect(main.getByText('当前条件下暂无投递记录')).toBeVisible()
    await expect(page.getByText('邮件已重新排队', { exact: true })).toBeVisible()
    await expect(page).toHaveURL(/\?kind=EMAIL_VERIFICATION&status=SENT&user_id=418$/)
    expect(Object.fromEntries(reads.at(-1) ?? [])).toEqual({ page: '1', page_size: '20', kind: 'EMAIL_VERIFICATION', status: 'SENT', user_id: '418' })
    expect(resends).toEqual([{ id: sentDeliveryId, payload: { resend_token: sentResendToken } }])
    expect(retries).toHaveLength(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
  })

  test(`read-only viewers can open current mail delivery details at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const { reads, retries, resends } = await mockMail(page, {
      ...profile, permission_codes: ['sys.user.view'], can_view_api_docs: false,
    })
    let detailReads = 0
    await page.route(`**${deliveryUrl}/${sentDeliveryId}`, route => {
      expect(route.request().method()).toBe('GET')
      const latest = { ...deliveryDetail(deliveries[1]!), attempts: ++detailReads + 1 }
      return route.fulfill({ json: latest })
    })
    await page.goto(`/#${monitorPath}?page=2`)
    const main = page.getByRole('main')
    const details = main.getByRole('button', { name: '查看详情', exact: true })
    await expect(details).toHaveCount(deliveries.length)
    await expect(main.getByRole('button', { name: '重发邮件', exact: true })).toHaveCount(0)
    await expect(main.getByRole('button', { name: '重新投递', exact: true })).toHaveCount(0)
    expect(detailReads).toBe(0)

    const row = (name: string) => main.locator(width === 375 ? '.delivery-card' : 'tbody tr').filter({ hasText: name })
    const sent = row('yan.operations').getByRole('button', { name: '查看详情', exact: true })
    if (width === 375) {
      expect((await sent.boundingBox())?.height).toBeGreaterThanOrEqual(44)
      await sent.click()
    } else {
      await sent.press('Enter')
    }
    const dialog = page.getByRole('dialog', { name: '投递详情' })
    const field = (label: string) => dialog.getByText(label, { exact: true }).locator('+ dd')
    await expect(field('收件人')).toContainText('yan.operations')
    await expect(field('投递时收件地址')).toHaveText(maskedRecipient)
    await expect(field('邮件事件')).toHaveText('验证通知邮箱')
    await expect(field('事件时间').locator('time')).toHaveAttribute('datetime', eventDate)
    await expect(field('投递创建时间').locator('time')).toHaveAttribute('datetime', date)
    await expect(field('尝试次数')).toHaveText('2')
    await expect(field('投递状态')).toContainText('SMTP 服务器已接受邮件，收件箱送达及阅读状态未知。')
    await expect(field('最近原因')).toHaveText('—')
    await expect(field('下次尝试')).toHaveText('—')
    const bounds = await dialog.boundingBox()
    expect(bounds?.x).toBeGreaterThanOrEqual(0)
    expect((bounds?.x ?? 0) + (bounds?.width ?? 0)).toBeLessThanOrEqual(width)
    await page.screenshot({ path: info.outputPath(`mail-detail-${width}.png`), animations: 'disabled' })

    const close = dialog.getByRole('button', { name: '关闭', exact: true })
    if (width === 375) {
      expect((await close.boundingBox())?.height).toBeGreaterThanOrEqual(44)
      await close.click()
    } else {
      await page.keyboard.press('Escape')
    }
    await expect(dialog).toBeHidden()
    await expect(sent).toBeFocused()
    await sent.click()
    await expect(field('尝试次数')).toHaveText('3')
    await close.click()
    await expect(dialog).toBeHidden()

    await row('李明').getByRole('button', { name: '查看详情', exact: true }).click()
    await expect(field('投递时收件地址')).toHaveText('暂无记录')
    await expect(field('投递状态')).toHaveText('等待重试')
    await expect(field('最近原因')).toHaveText('无法连接邮件服务器')
    await expect(field('下次尝试').locator('time')).toHaveAttribute('datetime', date)
    expect(detailReads).toBe(2)
    expect(reads).toHaveLength(1)
    expect(retries).toHaveLength(0)
    expect(resends).toHaveLength(0)
    await expect(page).toHaveURL(/\?page=2$/)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
  })
}

test('mail resend conflict refreshes the row without replaying the request', async ({ page }) => {
  const { reads, resends } = await mockMail(page, profile, { canResend: true, resendConflict: true })
  await page.goto(`/#${monitorPath}?user_id=418`)
  const main = page.getByRole('main')
  const resend = main.getByRole('button', { name: '重发邮件', exact: true })
  await resend.click()
  await page.getByRole('dialog', { name: '确认重发邮件' }).getByRole('button', { name: '确认重发', exact: true }).click()
  await expect(page.getByText('投递记录已变化，请查看最新状态。')).toBeVisible()
  await expect(resend).toBeDisabled()
  await expect(main.getByText('收件人已完成邮箱验证。')).toBeVisible()
  expect(reads.at(-1)?.get('user_id')).toBe('418')
  expect(resends).toHaveLength(1)
})

test('mail delivery detail recovers from a load failure and handles access denials inline', async ({ page }) => {
  const { reads } = await mockMail(page)
  const statuses = [503, 200, 403, 404]
  await page.route(`**${deliveryUrl}/${sentDeliveryId}`, route => {
    const status = statuses.shift()
    return route.fulfill({
      status,
      json: status === 200 ? deliveryDetail(deliveries[1]!) : { message: 'internal diagnostic' },
    })
  })
  await page.goto(`/#${monitorPath}?user_id=418`)
  const details = page.getByRole('button', { name: '查看详情', exact: true })
  const dialog = page.getByRole('dialog', { name: '投递详情' })
  const close = dialog.getByRole('button', { name: '关闭', exact: true })
  const retry = dialog.getByRole('button', { name: '重新加载', exact: true })
  await details.click()
  await expect(dialog.getByRole('alert')).toContainText('投递详情加载失败')
  await retry.click()
  await expect(dialog.getByText(maskedRecipient, { exact: true })).toBeVisible()
  await close.click()
  await expect(dialog).toBeHidden()

  for (const message of ['当前账号无权查看投递详情', '投递记录已无法查看']) {
    await details.click()
    await expect(dialog.getByRole('alert')).toContainText(message)
    await expect(dialog.getByText('internal diagnostic')).toHaveCount(0)
    await expect(dialog.getByText(maskedRecipient, { exact: true })).toHaveCount(0)
    await expect(retry).toHaveCount(0)
    await close.click()
    await expect(dialog).toBeHidden()
  }
  await expect(page).toHaveURL(/\?user_id=418$/)
  expect(reads).toHaveLength(1)
})

test('closing a loading delivery detail cancels it before another record opens', async ({ page }) => {
  await mockMail(page)
  let held: Route | undefined
  await page.route(`**${deliveryUrl}/${sentDeliveryId}`, route => { held = route })
  await page.goto(`/#${monitorPath}`)
  const details = (name: string) => page.locator('.delivery-table tbody tr').filter({ hasText: name }).getByRole('button', { name: '查看详情', exact: true })
  const dialog = page.getByRole('dialog', { name: '投递详情' })
  await details('yan.operations').click()
  await expect(dialog.getByRole('status')).toContainText('正在加载投递详情')
  await expect.poll(() => Boolean(held)).toBe(true)
  const canceled = page.waitForEvent('requestfailed', { predicate: request => request.url().endsWith(`/${sentDeliveryId}`) })
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  expect((await canceled).failure()?.errorText).toBe('net::ERR_ABORTED')
  await details('李明').click()
  await expect(dialog.getByText('李明', { exact: true })).toBeVisible()
  await held!.fulfill({ json: deliveryDetail(deliveries[1]!) })
  await expect(dialog.getByText('yan.operations', { exact: true })).toHaveCount(0)
})

test('unqualified users cannot open mail records directly or via navigation', async ({ page }) => {
  const { reads, lookups, retries } = await mockMail(page, { ...profile, permission_codes: ['sys.user.view'], can_view_mail_deliveries: false })
  await page.goto('/#/profile')
  await expect(page.getByRole('heading', { name: '个人中心' })).toBeVisible()
  await expect(page.getByRole('link', { name: '邮件记录', exact: true })).toHaveCount(0)
  await page.goto(`/#${monitorPath}`)
  await expect(page).toHaveURL(/#\/forbidden$/)
  expect(reads).toHaveLength(0)
  expect(lookups).toHaveLength(0)
  expect(retries).toHaveLength(0)
})
