import { mockCollaboration, mockReadPanels } from './collaboration-fixture'
import { expect, test } from '@playwright/test'

const member = {
  id: 42,
  username: 'member-with-a-long-username-for-mobile-layout',
  display_name: '普通成员',
  email: 'member-with-a-long-email-address@example.com',
  status: 'ACTIVE',
  revision: 1,
  must_change_password: false,
  data_scope: 'SELF',
  role_ids: [],
  permission_codes: ['dashboard.view', 'rd.feedback.view', 'rd.requirement.view', 'rd.version.view'],
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('profile-test-initialized')) {
      localStorage.setItem('iterflow.access_token', 'profile-test-access')
      localStorage.setItem('iterflow.refresh_token', 'profile-test-refresh')
      sessionStorage.setItem('profile-test-initialized', '1')
    }
  })
  await page.route('**/api/v1/announcements/notice', async route => { await mockReadPanels(route) })
  await page.route('**/api/v1/me/mail-preferences', async route => { await mockCollaboration(route) })
  await page.route('**/api/v1/me/wecom-preferences', async route => { await mockReadPanels(route) })
  await page.route('**/api/v1/notifications/unread-count', (route) => route.fulfill({ status: 200, json: { unread_count: 0 } }))
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({ status: 200, json: member }))
  await page.route('**/api/v1/auth/logout', (route) => route.fulfill({ status: 200, json: {} }))
})

test('profile remains usable at all five release viewports', async ({ page }) => {
  const browserErrors: string[] = []
  page.on('pageerror', (error) => browserErrors.push(error.message))
  await page.route('**/api/v1/requirements?*', (route) => route.fulfill({ status: 200, json: { items: [], total: 0, page: 1, page_size: 3 } }))
  await page.route('**/api/v1/dashboard/overview', (route) => route.fulfill({ status: 200, json: {
    data_scope: 'SELF', activities: [],
    feedback: { pending_count: 0, total_count: 0, by_status: {} },
    requirements: { active_count: 0, total_count: 0, by_status: {} },
    versions: { active_count: 0, total_count: 0, by_status: {}, recent_active_versions: [] },
    releases: null,
  } }))
  for (const width of [375, 390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/profile')
    await expect(page).toHaveURL(/\/#\/profile$/)
    await expect(page.getByRole('heading', { name: '个人中心' })).toBeVisible()
    await expect(page.getByText(member.username, { exact: true })).toBeVisible()
    await expect(page.getByText(member.email)).toBeVisible()
    await expect(page.getByRole('button', { name: '修改密码' })).toBeVisible()
    await expect(page.getByRole('main').getByRole('button', { name: '退出登录' })).toBeVisible()
    const geometry = await page.evaluate(() => {
      const card = document.querySelector('.profile-card')!.getBoundingClientRect()
      const nav = document.querySelector('.bottom')!.getBoundingClientRect()
      const button = document.querySelector('.actions .el-button:last-child')!.getBoundingClientRect()
      return {
        pageWidth: document.documentElement.scrollWidth,
        viewportWidth: window.innerWidth,
        cardLeft: card.left,
        cardRight: card.right,
        navTop: nav.top,
        buttonBottom: button.bottom,
      }
    })
    expect(geometry.pageWidth, `${width}px horizontal overflow`).toBeLessThanOrEqual(geometry.viewportWidth + 1)
    expect(geometry.cardLeft).toBeGreaterThanOrEqual(0)
    expect(geometry.cardRight).toBeLessThanOrEqual(width + 1)
    if (width < 768) {
      const nav = page.getByRole('navigation', { name: '主导航' })
      const destinations = [['反馈', '/feedbacks'], ['需求', '/requirements'], ['版本', '/versions'], ['消息', '/notifications'], ['我的', '/profile']] as const
      await expect(nav.getByRole('link')).toHaveCount(destinations.length)
      for (const [label, path] of destinations) {
        const link = nav.getByRole('link', { name: label, exact: true })
        await expect(link).toBeVisible()
        await expect(link).toHaveAttribute('href', `#${path}`)
      }
      const links = await nav.getByRole('link').all()
      const bounds = await Promise.all(links.map((link) => link.boundingBox()))
      for (const bound of bounds) {
        expect(bound).not.toBeNull()
        expect(bound!.width).toBeGreaterThanOrEqual(44)
        expect(bound!.height).toBeGreaterThanOrEqual(44)
        expect(bound!.x).toBeGreaterThanOrEqual(0)
        expect(bound!.x + bound!.width).toBeLessThanOrEqual(width + 1)
      }
      for (let index = 1; index < bounds.length; index += 1) {
        expect(bounds[index]!.x).toBeGreaterThanOrEqual(bounds[index - 1]!.x + bounds[index - 1]!.width - 1)
      }
      expect(geometry.buttonBottom).toBeLessThan(geometry.navTop)
      const home = page.locator('.mobile-header').getByRole('link', { name: '返回首页', exact: true })
      await expect(home).toBeVisible()
      await expect(home).toHaveAttribute('href', '#/')
      const overview = page.waitForResponse(response => response.url().endsWith('/api/v1/dashboard/overview'))
      await home.click()
      expect((await overview).status()).toBe(200)
      await expect(page).toHaveURL(/\/#\/$/)
      await expect(page.getByRole('heading', { name: '我的工作台', exact: true })).toBeVisible()
      await nav.getByRole('link', { name: '我的', exact: true }).click()
      await expect(page).toHaveURL(/\/#\/profile$/)
      await expect(page.getByRole('heading', { name: '个人中心', exact: true })).toBeVisible()
    }
  }
  expect(browserErrors).toEqual([])
})

test('profile password entry and logout work for a MEMBER without management permissions', async ({ page }) => {
  await page.goto('/#/profile')
  await page.getByRole('button', { name: '修改密码' }).click()
  await expect(page).toHaveURL(/\/#\/change-password\?from=profile$/)
  await expect(page.getByRole('heading', { name: '修改密码' })).toBeVisible()
  await page.goto('/#/profile')
  await page.getByRole('main').getByRole('button', { name: '退出登录' }).click()
  await expect(page).toHaveURL(/\/#\/login$/)
  expect(await page.evaluate(() => localStorage.getItem('iterflow.access_token'))).toBeNull()
})

test('an administrator can collapse mail deliveries while a retry is in progress', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.route('**/api/v1/auth/me', route => route.fulfill({
    json: { ...member, can_view_api_docs: true, permission_codes: ['sys.user.edit'] },
  }))
  let deliveryStatus = 'FAILED'
  let finishRetry!: () => void
  const retryGate = new Promise<void>(resolve => { finishRetry = resolve })
  const requestedPages: string[] = []
  await page.route('**/api/v1/admin/mail-deliveries?*', route => {
    requestedPages.push(new URL(route.request().url()).searchParams.get('page') ?? '')
    return route.fulfill({ json: [{ id: 'delivery-7', event_id: 'event-7', user_id: 42, channel: 'EMAIL', status: deliveryStatus, attempts: 1, last_error: null, next_attempt_at: '2026-11-26T08:00:00Z' }] })
  })
  const retryPath = '/admin/mail-deliveries/delivery-7/retry'
  await page.route(`**/api/v1${retryPath}`, async route => {
    await retryGate
    deliveryStatus = 'SENT'
    await route.fulfill({ status: 204 })
  })
  await page.goto('/#/profile')
  const toggle = page.getByRole('button', { name: /^(查看|收起)邮件投递记录$/ })
  const record = page.getByText(/用户 #42 · (发送失败|已发送)/)
  await expect(toggle).toHaveText('查看邮件投递记录')
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await expect(record).toBeHidden()
  expect(requestedPages).toEqual([])
  await toggle.click()
  await expect(toggle).toHaveText('收起邮件投递记录')
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  await expect(record).toContainText('发送失败')

  const retried = page.waitForResponse(response => response.url().endsWith(retryPath))

  try {
    await page.getByRole('button', { name: '重新投递' }).click()
    await toggle.click()
    await expect(record).toBeHidden()
    await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  } finally {
    finishRetry()
  }

  await retried
  await expect(toggle).toHaveText('查看邮件投递记录')
  await expect(record).toBeHidden()
  await toggle.press('Enter')
  await expect(record).toContainText('已发送')
  expect(requestedPages.length).toBeGreaterThanOrEqual(2)
  expect(requestedPages.every(page => page === '1')).toBe(true)
})

test('chooses a notification email with the keyboard before requesting verification', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const preferences = { revision: 3, mode: 'TASKS', email: member.email, verified: true, pending_email: null, smtp_enabled: true, notice_acknowledged: true }
  const requests: unknown[] = []
  await page.route('**/api/v1/me/mail-preferences', route => route.fulfill({ json: preferences }))
  await page.route('**/api/v1/me/email-verification', route => {
    requests.push(route.request().postDataJSON())
    return route.fulfill({ json: { ...preferences, revision: 4, pending_email: 'sample+alerts@gmail.com' } })
  })
  await page.goto('/#/profile')
  const email = page.getByRole('combobox', { name: '通知邮箱', exact: true })
  await expect(email).toHaveCount(0)
  await page.getByRole('button', { name: '重新验证', exact: true }).click()
  await expect(email).toHaveValue(member.email)

  const list = page.getByRole('listbox')
  await email.evaluate(element => element.scrollIntoView({ block: 'center' }))
  await email.fill('sample+alerts')
  await expect(list.getByRole('option', { name: 'sample+alerts@qq.com' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('notification-email-desktop.png'), animations: 'disabled' })
  await email.press('Escape')
  await expect(list).toBeHidden()
  await expect(email).toHaveValue('sample+alerts')

  await email.fill('sample+alerts@Gm')
  await expect(list.getByRole('option')).toHaveCount(1)
  await expect(list.getByRole('option')).toHaveText('sample+alerts@gmail.com')
  await email.press('ArrowDown')
  await email.press('Enter')
  await expect(list).toBeHidden()
  await expect(email).toHaveValue('sample+alerts@gmail.com')
  expect(requests).toEqual([])
  await page.getByRole('button', { name: '发送验证码', exact: true }).click()
  await expect(page.getByText('待验证地址：sample+alerts@gmail.com')).toBeVisible()
  expect(requests).toEqual([{ revision: 3, email: 'sample+alerts@gmail.com' }])
})

test.describe('notification email with touch input', () => {
  test.use({ viewport: { width: 375, height: 812 }, hasTouch: true })

  test('fits the field, selects with a tap, and keeps a custom domain', async ({ page }, testInfo) => {
    await page.goto('/#/profile')
    const email = page.getByRole('combobox', { name: '通知邮箱', exact: true })
    await expect(email).toHaveAttribute('inputmode', 'email')
    await email.scrollIntoViewIfNeeded()
    await email.fill('sample')
    const suggestions = page.getByRole('listbox')
    const firstOption = suggestions.getByRole('option', { name: 'sample@qq.com', exact: true })
    await expect(firstOption).toBeInViewport()
    const box = (await firstOption.boundingBox())!
    expect(box.x).toBeGreaterThanOrEqual(0)
    expect(box.x + box.width).toBeLessThanOrEqual(375)
    expect(box.height).toBeGreaterThanOrEqual(44)
    await page.screenshot({ path: testInfo.outputPath('notification-email-mobile.png'), animations: 'disabled' })
    await firstOption.tap()
    await expect(email).toHaveValue('sample@qq.com')
    await expect(suggestions).toBeHidden()

    await email.fill('sample@engineering.example.test')
    await expect(email).toHaveValue('sample@engineering.example.test')
    await expect(suggestions).toBeHidden()
  })
})
