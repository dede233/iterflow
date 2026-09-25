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
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({ status: 200, json: member }))
  await page.route('**/api/v1/auth/logout', (route) => route.fulfill({ status: 200, json: {} }))
})

test('profile remains usable at all five release viewports', async ({ page }) => {
  const browserErrors: string[] = []
  page.on('pageerror', (error) => browserErrors.push(error.message))
  for (const width of [375, 390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/profile')
    await expect(page).toHaveURL(/\/profile$/)
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
      for (const label of ['首页', '反馈', '需求', '版本', '消息', '我的']) {
        await expect(nav.getByRole('link', { name: label })).toBeVisible()
      }
      const links = await nav.getByRole('link').all()
      const bounds = await Promise.all(links.map((link) => link.boundingBox()))
      for (let index = 1; index < bounds.length; index += 1) {
        expect(bounds[index]!.x).toBeGreaterThanOrEqual(bounds[index - 1]!.x + bounds[index - 1]!.width - 1)
      }
      expect(geometry.buttonBottom).toBeLessThan(geometry.navTop)
    }
  }
  expect(browserErrors).toEqual([])
})

test('profile password entry and logout work for a MEMBER without management permissions', async ({ page }) => {
  await page.goto('/profile')
  await page.getByRole('button', { name: '修改密码' }).click()
  await expect(page).toHaveURL(/\/change-password\?from=profile$/)
  await expect(page.getByRole('heading', { name: '修改密码' })).toBeVisible()
  await page.goto('/profile')
  await page.getByRole('main').getByRole('button', { name: '退出登录' }).click()
  await expect(page).toHaveURL(/\/login$/)
  expect(await page.evaluate(() => localStorage.getItem('iterflow.access_token'))).toBeNull()
})
