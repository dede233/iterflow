import { expect, test } from '@playwright/test'
for (const width of [375, 390, 768, 1280, 1440]) {
  test(`badge refreshes on resume with cooldown at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const start = Date.parse('2026-10-02T00:00:00Z')
    await page.clock.setFixedTime(start)
    let requests = 0
    let count = 3
    await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'freshness'); localStorage.setItem('iterflow.refresh_token', 'freshness-refresh') })
    await page.route('**/api/v1/**', route => {
      const path = new URL(route.request().url()).pathname
      const json = (body: unknown) => route.fulfill({ json: body })
      if (path.endsWith('/auth/me')) return json({ id: 1, username: 'reader', display_name: '查看者', email: null, status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'SELF', role_ids: [], permission_codes: [] })
      if (path.endsWith('/notifications/unread-count')) { requests++; return json({ unread_count: count }) }
      return route.fulfill({ status: 500, json: { message: 'unexpected request' } })
    })
    await page.goto('/#/profile')
    const badge = page.locator('.notification-badge:visible')
    await expect(badge).toHaveText('3')
    expect(requests).toBe(1)
    count = 7
    await page.clock.setFixedTime(start + 29999)
    await page.evaluate(() => { for (let i = 0; i < 10; i++) window.dispatchEvent(new Event('focus')) })
    await expect(badge).toHaveText('3')
    await page.clock.setFixedTime(start + 30000)
    await page.evaluate(() => window.dispatchEvent(new Event('focus')))
    await expect(badge).toHaveText('7')
    expect(requests).toBe(2)
    count = 9
    await page.clock.setFixedTime(start + 60000)
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', { configurable: true, value: true })
      document.dispatchEvent(new Event('visibilitychange'))
      window.dispatchEvent(new Event('focus'))
    })
    await expect(badge).toHaveText('7')
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', { configurable: true, value: false })
      document.dispatchEvent(new Event('visibilitychange'))
      window.dispatchEvent(new Event('focus'))
    })
    await expect(badge).toHaveText('9')
    expect(requests).toBe(3)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
  })
}
