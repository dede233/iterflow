import { expect, test, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'

const appVersion = JSON.parse(
  readFileSync(new URL('../package.json', import.meta.url), 'utf8'),
).version as string

async function fixture(page: Page, expired: boolean) {
  let refreshCalls = 0
  await page.addInitScript(expired => {
    if (expired) {
      localStorage.setItem('iterflow.access_token', 'expired-v17-test')
      localStorage.setItem('iterflow.refresh_token', 'invalid-v17-test')
    }
  }, expired)
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown) => route.fulfill({ status: 200, json: body })
    if (path === '/api/v1/auth/refresh') {
      refreshCalls++
      return route.fulfill({ status: 401, json: { code: 40101, message: 'Invalid refresh' } })
    }
    if (path === '/api/v1/auth/login') return json({ access_token: 'fresh-v17-test', refresh_token: 'fresh-v17-refresh', token_type: 'bearer', must_change_password: false })
    if (path === '/api/v1/auth/me') {
      if (route.request().headers().authorization === 'Bearer expired-v17-test') return route.fulfill({ status: 401, json: { code: 40101, message: 'Expired access' } })
      return json({ id: 1, username: 'reader', display_name: '查看者', revision: 1, status: 'ACTIVE', data_scope: 'SELF', role_ids: [], must_change_password: false, permission_codes: ['rd.requirement.view', 'dashboard.view'] })
    }
    if (path === '/api/v1/notifications/unread-count') return json({ unread_count: 0 })
    if (path === '/api/v1/requirements') return json({ items: [], total: 0, page: 1, page_size: 20 })
    if (path === '/api/v1/dashboard/overview') return json({ data_scope: 'SELF', feedback: null, requirements: null, versions: null, releases: null, activities: [] })
    return route.fulfill({ status: 500, json: { message: 'Unexpected request' } })
  })
  return () => refreshCalls
}
async function login(page: Page) {
  await page.getByPlaceholder('用户名').fill('reader')
  await page.getByPlaceholder('密码').fill('mock-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()
}
for (const width of [375, 390, 768, 1280, 1440]) {
  test(`failed refresh preserves Hash destination and query at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const refreshCalls = await fixture(page, true)
    const target = '/requirements?tab=info&keyword=alpha'
    await page.goto(`/#${target}`)
    await expect(page.getByRole('heading', { name: '迭程 IterFlow', exact: true })).toBeVisible()
    const loginHash = new URL(page.url()).hash
    expect(loginHash.split('?')[0]).toBe('#/login')
    expect(new URLSearchParams(loginHash.slice(loginHash.indexOf('?') + 1)).get('redirect')).toBe(target)
    expect(refreshCalls()).toBe(1)
    if (width >= 768) await expect(page.locator('.auth-foot')).toHaveText(`ITERFLOW / V${appVersion}`)
    await login(page)
    await expect(page.getByRole('heading', { name: '需求管理', exact: true })).toBeVisible()
    expect(new URL(page.url()).hash).toBe(`#${target}`)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
  })
}
test('login rejects an external query destination', async ({ page }) => {
  await fixture(page, false)
  await page.goto('/#/login?redirect=https%3A%2F%2Fevil.example')
  await login(page)
  await expect(page.getByRole('heading', { name: '首页 / 系统概览', exact: true })).toBeVisible()
  expect(new URL(page.url()).hash).toBe('#/')
})
