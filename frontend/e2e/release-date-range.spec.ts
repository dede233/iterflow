import { expect, test } from '@playwright/test'
test.use({ timezoneId: 'America/New_York' })
for (const width of [375, 390, 768, 1280, 1440]) {
  test(`Release local date range, DST and popper lifecycle at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const requests: Record<string, string>[] = []
    await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'release-dates'); localStorage.setItem('iterflow.refresh_token', 'release-dates-refresh') })
    await page.route('**/api/v1/**', route => {
      const url = new URL(route.request().url())
      const json = (body: unknown) => route.fulfill({ json: body })
      if (url.pathname.endsWith('/auth/me')) return json({ id: 1, username: 'reader', display_name: '查看者', status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'SELF', role_ids: [], permission_codes: ['rd.release.view'] })
      if (url.pathname.endsWith('/notifications/unread-count')) return json({ unread_count: 0 })
      if (url.pathname === '/api/v1/releases') {
        const params = Object.fromEntries(url.searchParams); requests.push(params)
        const matched = params.version_id === '42' && params.released_from === '2026-03-08T05:00:00.000Z' && params.released_before === '2026-03-09T04:00:00.000Z'
        return json({ items: matched ? [{ id: 1, version_id: 42, released_at: '2026-03-08T12:00:00Z', result: 'SUCCESS', release_notes: '日期命中发布' }] : [], total: matched ? 41 : 0, page: Number(params.page), page_size: 20 })
      }
      return route.fulfill({ status: 500, json: { message: 'unexpected' } })
    })
    await page.goto('/#/releases')
    await expect(page.getByRole('heading', { name: '发布记录', exact: true })).toBeVisible()
    await expect.poll(() => requests.at(-1)).toEqual({ page: '1', page_size: '20' })
    if (width < 768) await page.getByRole('button', { name: '筛选', exact: true }).click()
    const form = width < 768 ? page.locator('.el-drawer:visible') : page.locator('.list-filters')
    await form.locator('.el-input-number input').fill('42')
    await form.locator('.el-input-number input').press('Tab')
    await form.getByPlaceholder('开始日期').click()
    const popper = page.locator('.el-picker__popper:visible')
    await expect(popper).toHaveCount(1)
    await expect(popper.locator('.el-date-range-picker')).toContainText(/\d{4}\s*年/)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    await page.keyboard.press('Escape')
    await expect(popper).toHaveCount(0)
    await form.getByPlaceholder('开始日期').fill('2026-03-08')
    await form.getByPlaceholder('结束日期').fill('2026-03-08')
    await form.getByPlaceholder('结束日期').press('Tab')
    await expect(popper).toHaveCount(0)
    await form.getByRole('button', { name: '查询', exact: true }).click()
    const bounds = { version_id: '42', released_from: '2026-03-08T05:00:00.000Z', released_before: '2026-03-09T04:00:00.000Z' }
    await expect.poll(() => requests.at(-1)).toEqual({ page: '1', page_size: '20', ...bounds })
    await expect(page.getByText('日期命中发布', { exact: true })).toBeVisible()
    if (width < 768) await expect(page.locator('.el-drawer:visible')).toHaveCount(0)
    await page.locator('.el-pagination .number').filter({ hasText: /^2$/ }).click()
    await expect.poll(() => requests.at(-1)).toEqual({ page: '2', page_size: '20', ...bounds })
    if (width < 768) await page.getByRole('button', { name: '筛选', exact: true }).click()
    await form.getByRole('button', { name: '重置', exact: true }).click()
    await expect.poll(() => requests.at(-1)).toEqual({ page: '1', page_size: '20' })
    await expect(page.getByText('日期命中发布', { exact: true })).toHaveCount(0)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
  })
}
