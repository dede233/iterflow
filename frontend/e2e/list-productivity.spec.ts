import { expect, test, type Locator, type Page } from '@playwright/test'

const configs = [
  { path: 'requirements', permission: 'rd.requirement.view', title: '需求管理', drawer: '筛选需求', result: '筛选命中需求', row: { requirement_no: 'REQ-77', title: '筛选命中需求', priority: 'P1', source: 'FEEDBACK', status: 'CONFIRMED' }, params: { keyword: 'hit', status: 'CONFIRMED' } },
  { path: 'versions', permission: 'rd.version.view', title: '版本管理', drawer: '筛选版本', result: '筛选命中版本', row: { version_no: 'V1.6.0', name: '筛选命中版本', planned_release_date: '2026-10-02', status: 'RELEASED' }, params: { status: 'RELEASED', planned_release_from: '2026-10-01', planned_release_to: '2026-10-03' } },
  { path: 'releases', permission: 'rd.release.view', title: '发布记录', drawer: '筛选发布记录', result: '筛选命中发布', row: { version_id: 42, release_notes: '筛选命中发布', result: 'SUCCESS', released_at: '2026-10-01T00:00:00Z' }, params: { version_id: '42' } },
] as const

async function fixture(page: Page, config: typeof configs[number]) {
  const requests: Record<string, string>[] = []
  const unexpected: string[] = []
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'list-productivity-access')
    localStorage.setItem('iterflow.refresh_token', 'list-productivity-refresh')
  })
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url())
    const json = (body: unknown) => route.fulfill({ status: 200, json: body })
    if (url.pathname === '/api/v1/auth/me') return json({ id: 1, username: 'reader', display_name: '普通查看者', status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'SELF', role_ids: [], permission_codes: [config.permission] })
    if (url.pathname === '/api/v1/notifications/unread-count') return json({ unread_count: 0 })
    if (url.pathname === `/api/v1/${config.path}`) {
      const params = Object.fromEntries(url.searchParams.entries())
      requests.push(params)
      const matched = Object.entries(config.params).every(([key, value]) => params[key] === value)
      return json({ items: matched ? [{ id: 77, ...config.row }] : [], total: matched ? 41 : 0, page: Number(params.page), page_size: 20 })
    }
    if (url.pathname === '/api/v1/releases/77') return json({ id: 77, version_id: 42, release_notes: '筛选命中发布', rollback_notes: null, result: 'SUCCESS', released_at: '2026-10-01T00:00:00Z', created_at: '2026-10-01T00:00:00Z', created_by: null, revision: 1 })
    unexpected.push(url.pathname)
    return route.fulfill({ status: 500, json: { detail: 'unexpected request' } })
  })
  return { requests, unexpected }
}

async function selectStatus(page: Page, form: Locator, label: string) {
  await form.locator('.el-form-item').filter({ hasText: /^状态/ }).locator('.el-select').click()
  await page.locator('.el-select-dropdown:visible').getByText(label, { exact: true }).click()
}

async function filterForm(page: Page, width: number, config: typeof configs[number]) {
  if (width >= 768) return page.locator('.list-filters')
  await page.getByRole('button', { name: '筛选', exact: true }).click()
  const drawer = page.locator('.el-drawer:visible')
  await expect(drawer.getByText(config.drawer, { exact: true })).toBeVisible()
  return drawer
}

for (const width of [375, 390, 768, 1280, 1440]) {
  for (const config of configs) {
    test(`${config.path} filters and pagination at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      const state = await fixture(page, config)
      await page.goto(`/#/${config.path}`)
      await expect(page.getByRole('heading', { name: config.title, exact: true })).toBeVisible()
      await expect.poll(() => state.requests.length).toBe(1)
      expect(state.requests[0]).toEqual({ page: '1', page_size: '20' })
      const form = await filterForm(page, width, config)
      if (config.path === 'requirements') {
        await form.getByPlaceholder('编号 / 标题').fill(' hit ')
        await selectStatus(page, form, '已确认')
      } else if (config.path === 'versions') {
        await selectStatus(page, form, '已发布')
        await form.getByPlaceholder('开始日期').click()
        const popper = page.locator('.version-filter-date-popper:visible')
        await expect(popper).toHaveCount(1)
        await expect(popper).toContainText(/\d{4}\s*年/)
        await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
        await page.keyboard.press('Escape')
        await expect(popper).toHaveCount(0)
        await form.getByPlaceholder('开始日期').fill('2026-10-01')
        await form.getByPlaceholder('结束日期').fill('2026-10-03')
        await form.getByPlaceholder('结束日期').press('Tab')
        await expect(popper).toHaveCount(0)
      } else {
        await form.locator('.el-input-number input').fill('42')
        await form.locator('.el-input-number input').press('Tab')
      }
      await form.getByRole('button', { name: '查询', exact: true }).click()
      await expect.poll(() => state.requests.at(-1)).toEqual({ page: '1', page_size: '20', ...config.params })
      await expect(page.getByText(config.result, { exact: true })).toBeVisible()
      if (width < 768) await expect(page.locator('.el-drawer:visible')).toHaveCount(0)
      await page.locator('.el-pagination .number').filter({ hasText: /^2$/ }).click()
      await expect.poll(() => state.requests.at(-1)).toEqual({ page: '2', page_size: '20', ...config.params })
      const resetForm = await filterForm(page, width, config)
      await resetForm.getByRole('button', { name: '重置', exact: true }).click()
      await expect.poll(() => state.requests.at(-1)).toEqual({ page: '1', page_size: '20' })
      await expect(page.getByText(config.result, { exact: true })).toHaveCount(0)
      if (width < 768) await expect(page.locator('.el-drawer:visible')).toHaveCount(0)
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
      if (config.path === 'releases') {
        const again = await filterForm(page, width, config)
        await again.locator('.el-input-number input').fill('42')
        await again.locator('.el-input-number input').press('Tab')
        await again.getByRole('button', { name: '查询', exact: true }).click()
        await expect(page.getByRole('button', { name: '查看详情', exact: true })).toBeVisible()
        await expect(page.getByRole('button', { name: '查看版本', exact: true })).toHaveCount(0)
        await page.getByRole('button', { name: '查看详情', exact: true }).click()
        await expect(page).toHaveURL(/\/#\/releases\/77$/)
        await expect(page.getByText('版本 #42', { exact: true })).toBeVisible()
        await expect(page.getByRole('heading', { name: '发布记录详情', exact: true })).toBeVisible()
      }
      expect(state.unexpected).toEqual([])
    })
  }
}
