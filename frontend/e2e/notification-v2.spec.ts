import { expect, test, type Page } from '@playwright/test'

async function notifications(page: Page, count: number, permissions = ['rd.release.view']) {
  const state = { count, countRequests: 0, reads: 0, all: 0, readAt: null as string | null, navigatedBeforeRead: false }
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'notification-v2-access')
    localStorage.setItem('iterflow.refresh_token', 'notification-v2-refresh')
  })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown) => route.fulfill({ status: 200, json: body })
    if (path === '/api/v1/auth/me') return json({ id: 1, username: 'member', display_name: '普通成员', email: null, status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'SELF', role_ids: [], permission_codes: permissions })
    if (path === '/api/v1/notifications/unread-count') {
      state.countRequests++
      return json({ unread_count: state.count })
    }
    if (path === '/api/v1/notifications') return json([{ id: 1, type: 'RELEASE', title: '版本发布通知'.repeat(12), content: '长通知内容用于响应式验收'.repeat(25), entity_type: 'RELEASE', entity_id: 99, read_at: state.readAt, created_at: '2026-10-01T00:00:00Z' }])
    if (path === '/api/v1/notifications/1/read') {
      state.reads++
      if (!state.readAt) state.count--
      state.readAt = '2026-10-01T01:00:00Z'
      return json({ ok: true })
    }
    if (path === '/api/v1/notifications/read-all') {
      state.all++
      const updated_count = state.count
      state.count = 0
      state.readAt = '2026-10-01T01:00:00Z'
      return json({ updated_count })
    }
    if (path === '/api/v1/releases') {
      if (!state.reads) state.navigatedBeforeRead = true
      return json([])
    }
    throw new Error(`Unexpected request: ${path}`)
  })
  return state
}

function visibleNav(page: Page, width: number) {
  return width < 768 ? page.getByRole('navigation', { name: '主导航' }) : page.getByRole('complementary', { name: '侧边导航' })
}

for (const width of [375, 390, 768, 1280, 1440]) {
  test(`notification total and read-all badges fit ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const state = await notifications(page, 125, [])
    await page.goto('/#/notifications')
    const nav = visibleNav(page, width)
    await expect(nav.locator('.notification-badge')).toHaveText('99+')
    await expect(page.getByText('125 条未读', { exact: true })).toBeVisible()
    await expect(page.locator('.notification-card')).toHaveCount(1)
    expect(state.countRequests).toBe(1)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    await page.getByRole('button', { name: '全部已读', exact: true }).click()
    await expect(page.getByText('0 条未读', { exact: true })).toBeVisible()
    await expect(nav.locator('.notification-badge')).toHaveCount(0)
    await expect(page.locator('.unread-dot')).toHaveCount(0)
    expect(state.all).toBe(1)
  })
}

for (const width of [375, 1440]) {
  test(`read precedes navigation and changes badge from 2 to 1 at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const state = await notifications(page, 2)
    await page.goto('/#/notifications')
    await expect(visibleNav(page, width).locator('.notification-badge')).toHaveText('2')
    await page.locator('.notification-card').click()
    await expect(page).toHaveURL(/\/#\/releases$/)
    await expect(visibleNav(page, width).locator('.notification-badge')).toHaveText('1')
    expect(state.reads).toBe(1)
    expect(state.navigatedBeforeRead).toBe(false)
  })
}

test('notification does not bypass revoked target permissions', async ({ page }) => {
  const state = await notifications(page, 2, [])
  await page.goto('/#/notifications')
  await expect(page.getByText('2 条未读', { exact: true })).toBeVisible()
  await page.locator('.notification-card').click()
  await expect(page).toHaveURL(/\/#\/forbidden$/)
  expect(state.reads).toBe(1)
  expect(state.count).toBe(1)
})
