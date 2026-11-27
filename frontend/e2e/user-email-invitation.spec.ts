import { expect, test, type Page } from '@playwright/test'
import type { components } from '../src/types/openapi.generated'
import { mockReadPanels } from './collaboration-fixture'

type User = components['schemas']['UserOut']
type Operator = components['schemas']['AuthMe']
type Invitation = components['schemas']['UserCreated']['verification_invitation']

const superAdmin: Operator = {
  id: 1, username: 'admin', display_name: '超级管理员', email: null, status: 'ACTIVE',
  revision: 1, must_change_password: false, data_scope: 'ALL', role_ids: [1], permission_codes: ['*'],
}
const member: Operator = {
  ...superAdmin, id: 21, username: 'new-member', display_name: '新同事', email: 'member@example.test',
  data_scope: 'SELF', role_ids: [], permission_codes: [],
}

function account(id: number, values: Partial<User> = {}): User {
  return {
    id, username: `account-${id}`, display_name: `账号 ${id}`, email: `account-${id}@example.test`,
    status: 'ACTIVE', revision: 3, role_ids: [], email_verification_status: 'UNVERIFIED', ...values,
  }
}

async function mockAdministration(page: Page, operator = superAdmin, invitation: Invitation = 'QUEUED') {
  const rows = [
    account(1, { email_verification_status: 'VERIFIED' }),
    account(2, { email_verification_status: 'PENDING' }),
    account(3, { email_verification_status: 'FAILED' }),
    account(4, { status: 'DISABLED' }),
    account(5, { email: null, email_verification_status: 'NO_EMAIL' }),
    ...Array.from({ length: 15 }, (_, i) => account(i + 6)),
  ]
  const olderAccount = account(21)
  const writes: unknown[] = []
  const creations: unknown[] = []
  const requestedPages: number[] = []
  let blocked = false
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'user-invitation-admin-token')
    localStorage.setItem('iterflow.refresh_token', 'user-invitation-admin-refresh')
  })
  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const { pathname, searchParams } = new URL(request.url())
    switch (pathname) {
      case '/api/v1/auth/me':
        return route.fulfill({ json: operator })
      case '/api/v1/notifications/unread-count':
        return route.fulfill({ json: { unread_count: 0 } })
      case '/api/v1/me/mail-preferences':
        return route.fulfill({ json: { revision: 1, mode: 'TASKS', email: operator.email, verified: false, pending_email: null, smtp_enabled: true, notice_acknowledged: true } })
      case '/api/v1/roles':
        return route.fulfill({ json: [{ id: 1, code: 'SUPER_ADMIN', name: '超级管理员', enabled: true, is_system: true }] })
      case '/api/v1/users': {
        if (request.method() === 'POST') {
          const body = request.postDataJSON()
          creations.push(body)
          const created = account(22, {
            username: body.username,
            email: body.email,
            display_name: body.display_name,
            email_verification_status: invitation === 'QUEUED' ? 'PENDING' : 'UNVERIFIED',
          })
          rows.unshift(created)
          return route.fulfill({ json: { ...created, verification_invitation: invitation } })
        }
        const requestedPage = Number(searchParams.get('page'))
        const size = Number(searchParams.get('page_size'))
        requestedPages.push(requestedPage)
        expect(size).toBe(20)
        const all = [...rows, olderAccount]
        return route.fulfill({ json: { items: all.slice((requestedPage - 1) * size, requestedPage * size), total: all.length, page: requestedPage, page_size: size } })
      }
      case '/api/v1/users/21/email-verification': {
        expect(request.method()).toBe('POST')
        const body = request.postDataJSON()
        writes.push(body)
        if (body.revision !== olderAccount.revision) {
          return route.fulfill({ status: 409, json: { code: 40910, message: '账号已变更' } })
        }
        if (blocked) {
          return route.fulfill({ status: 429, json: { code: 42970, message: '发送过于频繁，请稍后再试。' } })
        }
        olderAccount.email_verification_status = 'PENDING'
        blocked = true
        return route.fulfill({ status: 204 })
      }
    }
    if (await mockReadPanels(route)) return
    throw new Error(`Unexpected API request: ${request.method()} ${pathname}`)
  })
  return { writes, creations, requestedPages, changeEmail: () => { olderAccount.revision++; olderAccount.email = 'updated@example.test' } }
}

const sendButtonName = '发送验证邮件'
for (const width of [375, 1440]) {
  test(`shows mailbox state and sends to a paged account at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    const server = await mockAdministration(page)
    await page.goto('/#/system/users')
    await expect(page.getByText('共 21 个账号')).toBeVisible()
    const row = (id: number) => page.locator('tr, .user-card').filter({ has: page.getByText(`账号 ${id}`, { exact: true }) })
    for (const [id, label] of [[1, '已验证'], [2, '待验证'], [3, '发送失败'], [4, '未验证'], [5, '未设置邮箱']] as const) {
      await expect(row(id).getByText(label, { exact: true })).toBeVisible()
      await expect(row(id).getByRole('button', { name: sendButtonName })).toHaveCount(id === 2 || id === 3 ? 1 : 0)
    }
    const pager = page.getByLabel('账号列表分页')
    await pager.getByText('2', { exact: true }).click()
    const send = row(21).getByRole('button', { name: sendButtonName })
    await expect(send).toBeVisible()
    expect(server.requestedPages).toEqual([1, 2])
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    if (width === 375) expect((await send.boundingBox())?.height).toBeGreaterThanOrEqual(44)

    server.changeEmail()
    await send.click()
    await expect(page.getByText('该账号已更新，请核对最新邮箱后重新发送验证邮件。')).toBeVisible()
    await expect(row(21).getByText('updated@example.test', { exact: true })).toBeVisible()
    expect(server.writes).toEqual([{ revision: 3 }])
    await send.click()
    await expect(page.getByText('验证邮件已排队。', { exact: true })).toBeVisible()
    await expect(row(21).getByText('待验证', { exact: true })).toBeVisible()
    expect(server.writes).toEqual([{ revision: 3 }, { revision: 4 }])
    await expect(send).toBeEnabled()
    await page.screenshot({ path: testInfo.outputPath('user-email-verification.png'), animations: 'disabled' })
    await send.click()
    await expect(page.getByText('发送过于频繁，请稍后再试。')).toBeVisible()
  })
}

test('still shows verification status for an editor without the SUPER_ADMIN role', async ({ page }) => {
  const server = await mockAdministration(page, { ...superAdmin, role_ids: [], can_view_api_docs: true })
  await page.goto('/#/system/users')
  await expect(page.getByText('待验证', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: sendButtonName })).toHaveCount(0)
  expect(server.writes).toEqual([])
})

for (const invitation of ['QUEUED', 'FAILED'] as const) {
  test(`account creation reports the ${invitation} verification invitation independently`, async ({ page }) => {
    await page.setViewportSize({ width: invitation === 'QUEUED' ? 1440 : 375, height: 900 })
    const server = await mockAdministration(page, superAdmin, invitation)
    await page.goto('/#/system/users')
    const create = page.getByRole('button', { name: '创建用户', exact: true })
    await create.click()
    const dialog = page.getByRole('dialog', { name: '创建用户' })
    const username = dialog.getByLabel('用户名')
    const password = dialog.getByLabel('初始密码')
    const save = dialog.getByRole('button', { name: '保存', exact: true })
    await expect(password).toHaveValue('')
    await dialog.getByLabel('显示名称').fill('新同事')
    const email = dialog.getByLabel('邮箱', { exact: true })
    const expectedEmail = invitation === 'QUEUED' ? 'new-user@qq.com' : 'new-user@example.test'
    if (invitation === 'QUEUED') {
      await email.fill('new-user@q')
      const option = page.getByRole('option', { name: expectedEmail, exact: true })
      await expect(option).toBeVisible()
      await email.press('Escape')
      await expect(option).toBeHidden()
      await expect(dialog).toBeVisible()
      await email.fill('new-user')
      await option.click()
      await expect(email).toHaveValue(expectedEmail)
      expect(server.creations).toEqual([])
    } else {
      await email.fill(expectedEmail)
    }
    const expectedPassword = invitation === 'QUEUED' ? 'new-user123' : 'synthetic-password'
    if (invitation === 'QUEUED') {
      await username.fill('first-user')
      await expect(password).toHaveValue('first-user123')
      await username.clear()
      await expect(password).toHaveValue('')
    } else {
      await username.fill('tiny')
      await expect(password).toHaveValue('tiny123')
      await save.click()
      await expect(page.getByText('默认密码不足 8 个字符，请手动设置至少 8 个字符的初始密码。')).toBeVisible()
      expect(server.creations).toEqual([])
      await password.fill(expectedPassword)
    }
    await username.fill(' new-user ')
    await expect(password).toHaveValue(expectedPassword)
    await save.click()
    await expect(dialog).toBeHidden()
    await expect(page.getByText('新同事', { exact: true })).toBeVisible()
    expect(server.creations).toMatchObject([{ username: 'new-user', password: expectedPassword, email: expectedEmail }])
    await expect(page.getByText(invitation === 'QUEUED'
      ? '用户已创建，验证邮件已排队。'
      : '用户已创建，验证邮件入队失败。可在用户列表重新发送。')).toBeVisible()
    await create.click()
    await expect(username).toHaveValue('')
    await expect(password).toHaveValue('')
    await username.fill('another-user')
    await expect(password).toHaveValue('another-user123')
  })
}

test('the mail invitation deep link survives login and required initial password change', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 700 })
  let forced = true
  await page.route('**/api/v1/**', async route => {
    const { pathname } = new URL(route.request().url())
    switch (pathname) {
      case '/api/v1/auth/change-password':
        forced = false
        return route.fulfill({ json: { access_token: 'member-fresh', refresh_token: 'member-refresh', must_change_password: false } })
      case '/api/v1/auth/login':
        return route.fulfill({ json: { access_token: 'member-initial', refresh_token: 'member-refresh', must_change_password: true } })
      case '/api/v1/auth/me':
        return route.fulfill({ json: { ...member, must_change_password: forced } })
      case '/api/v1/me/mail-preferences':
        return route.fulfill({ json: { revision: 2, mode: 'TASKS', email: member.email, verified: false, pending_email: member.email, smtp_enabled: true, notice_acknowledged: true } })
      case '/api/v1/notifications/unread-count':
        return route.fulfill({ json: { unread_count: 0 } })
    }
    if (await mockReadPanels(route)) return
    throw new Error(`Unexpected API request: ${route.request().method()} ${pathname}`)
  })
  await page.goto('/#/profile#mail-notifications')
  await page.getByPlaceholder('用户名').fill('new-member')
  await page.getByPlaceholder('密码').fill('synthetic-initial-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('heading', { name: '修改初始密码' })).toBeVisible()
  await page.getByLabel('当前密码', { exact: true }).fill('synthetic-initial-password')
  await page.getByLabel('新密码', { exact: true }).fill('synthetic-new-password')
  await page.getByLabel('确认新密码', { exact: true }).fill('synthetic-new-password')
  await page.getByRole('button', { name: '保存新密码' }).click()
  await expect(page).toHaveURL(/\/#\/profile#mail-notifications$/)
  const preferences = page.locator('#mail-notifications')
  await expect(preferences.getByRole('heading', { name: '邮件通知' })).toBeInViewport()
  await expect(preferences.getByText('待验证地址：member@example.test')).toBeVisible()
  await expect(preferences.getByRole('button', { name: '验证邮箱', exact: true })).toBeVisible()
})
