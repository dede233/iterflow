import { mockReadPanels } from './collaboration-fixture'
import { expect, test, type Locator, type Page } from '@playwright/test'

async function fixture(page: Page, domain: 'requirements' | 'versions', restricted = false) {
  const lists: Record<string, string>[] = []
  const options: { path: string; params: Record<string, string> }[] = []
  const unexpected: string[] = []
  const versionLabel = restricted ? '版本 #31(无查看权限)' : 'V3.1 · 筛选版本'
  const labels: Record<string, { id: number; label: string }> = {
    versions: { id: 31, label: versionLabel }, participants: { id: 41, label: '历史参与人(已停用)' }, owners: { id: 51, label: '历史负责人(已停用)' },
  }
  await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'filter-access'); localStorage.setItem('iterflow.refresh_token', 'filter-refresh') })
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url()), path = url.pathname
    const params = Object.fromEntries(url.searchParams)
    const json = (data: unknown) => route.fulfill({ status: 200, json: data })
    if (path === '/api/v1/auth/me') return json({ id: 1, username: 'reader', display_name: '查看者', status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'SELF', role_ids: [], permission_codes: restricted ? ['rd.requirement.view'] : ['rd.requirement.view', 'rd.version.view'] })
    if (path === '/api/v1/me/mail-preferences') return json({ revision: 1, mode: 'TASKS', email: null, verified: false, pending_email: null, smtp_enabled: false })
    if (path === '/api/v1/notifications/unread-count') return json({ unread_count: 0 })
    if (path === `/api/v1/${domain}`) {
      lists.push(params)
      return json({ items: [], total: 0, page: Number(params.page), page_size: 20 })
    }
    const match = path.match(/^\/api\/v1\/(requirements|versions)\/filter-options\/(versions|participants|owners)$/)
    if (match) {
      options.push({ path, params })
      const selected = labels[match[2]]!
      if (params.selected_id) return json({ items: Number(params.selected_id) === selected.id ? [selected] : [], total: 1, page: 1, page_size: 20 })
      const searched = !!params.keyword
      const second = params.page === '2'
      const items = searched ? second ? [selected] : Array.from({ length: 20 }, (_, i) => ({ id: i + 101, label: `${params.keyword}候选${i + 1}` })) : [selected]
      return json({ items, total: searched ? 21 : 1, page: Number(params.page), page_size: 20 })
    }
    if (await mockReadPanels(route)) return
    unexpected.push(`${route.request().method()} ${path}`)
    return route.fulfill({ status: 500, json: { message: 'unexpected request' } })
  })
  return { lists, options, unexpected, versionLabel }
}

async function form(page: Page, width: number) {
  if (width >= 768) return page.locator('.list-filters')
  await page.getByRole('button', { name: '筛选', exact: true }).click()
  return page.locator('.el-drawer:visible')
}

function field(panel: Locator, label: string) {
  return panel.locator('.el-form-item').filter({ has: panel.page().locator('.el-form-item__label', { hasText: new RegExp(`^${label}$`) }) }).locator('.el-select')
}

async function chooseSecond(page: Page, panel: Locator, label: string, keyword: string, name: string) {
  const select = field(panel, label)
  await select.getByRole('combobox').click()
  await select.getByRole('combobox').fill(keyword)
  await expect(select.getByRole('combobox')).toHaveValue(keyword)
  const popper = page.locator('.el-select__popper:visible')
  await expect(popper.getByRole('option', { name: `${keyword}候选1`, exact: true })).toBeVisible()
  await popper.getByRole('button', { name: '下一页', exact: true }).click()
  await expect(popper.getByText('2 / 2', { exact: true })).toBeVisible()
  await popper.getByRole('option', { name, exact: true }).click()
  await expect(select).toContainText(name)
}

async function clear(panel: Locator, label: string) {
  const select = field(panel, label)
  await select.hover()
  await select.locator('.el-select__clear').click()
}

for (const width of [375, 1440]) {
  test(`requirement scoped version/participant selection, paging, URL restore and clear at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    const state = await fixture(page, 'requirements')
    await page.goto('/#/requirements')
    await expect(page.getByRole('heading', { name: '需求管理', exact: true })).toBeVisible()
    let panel = await form(page, width)
    await chooseSecond(page, panel, '版本', '版本', state.versionLabel)
    await chooseSecond(page, panel, '参与人', '历史', '历史参与人(已停用)')
    await panel.getByRole('button', { name: '查询', exact: true }).click()
    await expect.poll(() => state.lists.at(-1)).toEqual({ page: '1', page_size: '20', current_version_id: '31', participant_id: '41' })
    await expect(page).toHaveURL(/current_version_id=31&participant_id=41/)
    expect(state.options.some(o => o.path.endsWith('/versions') && o.params.keyword === '版本' && o.params.page === '2')).toBe(true)
    expect(state.options.some(o => o.path.endsWith('/participants') && o.params.keyword === '历史' && o.params.page === '2')).toBe(true)
    await page.reload()
    await expect(page.getByRole('heading', { name: '需求管理', exact: true })).toBeVisible()
    panel = await form(page, width)
    await expect(field(panel, '版本')).toContainText(state.versionLabel)
    await expect(field(panel, '参与人')).toContainText('历史参与人(已停用)')
    expect(state.options.some(o => o.params.selected_id === '31')).toBe(true)
    expect(state.options.some(o => o.params.selected_id === '41')).toBe(true)
    await clear(panel, '版本'); await clear(panel, '参与人')
    await panel.getByRole('button', { name: '查询', exact: true }).click()
    await expect.poll(() => state.lists.at(-1)).toEqual({ page: '1', page_size: '20' })
    await expect(page).toHaveURL(/\/#\/requirements$/)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    expect(state.unexpected).toEqual([])
  })

  test(`version owner remote paging, URL restore and reset at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    const state = await fixture(page, 'versions')
    await page.goto('/#/versions')
    await expect(page.getByRole('heading', { name: '版本管理', exact: true })).toBeVisible()
    let panel = await form(page, width)
    await chooseSecond(page, panel, '负责人', '历史', '历史负责人(已停用)')
    await panel.getByRole('button', { name: '查询', exact: true }).click()
    await expect.poll(() => state.lists.at(-1)).toEqual({ page: '1', page_size: '20', owner_id: '51' })
    await expect(page).toHaveURL(/\/#\/versions\?owner_id=51$/)
    await page.reload()
    await expect(page.getByRole('heading', { name: '版本管理', exact: true })).toBeVisible()
    panel = await form(page, width)
    await expect(field(panel, '负责人')).toContainText('历史负责人(已停用)')
    expect(state.options.some(o => o.params.selected_id === '51')).toBe(true)
    await clear(panel, '负责人')
    await panel.getByRole('button', { name: '查询', exact: true }).click()
    await expect.poll(() => state.lists.at(-1)).toEqual({ page: '1', page_size: '20' })
    await page.goto('/#/versions?owner_id=51')
    panel = await form(page, width)
    await panel.getByRole('button', { name: '重置', exact: true }).click()
    await expect(page).toHaveURL(/\/#\/versions$/)
    await expect.poll(() => state.lists.at(-1)).toEqual({ page: '1', page_size: '20' })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    expect(state.unexpected).toEqual([])
  })

  test(`requirement-view-only filters use safe scoped version labels at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    const state = await fixture(page, 'requirements', true)
    await page.goto('/#/requirements?current_version_id=31')
    await expect(page.getByRole('heading', { name: '需求管理', exact: true })).toBeVisible()
    const panel = await form(page, width)
    await expect(field(panel, '版本')).toContainText(state.versionLabel)
    await field(panel, '版本').getByRole('combobox').click()
    await expect(page.getByRole('option', { name: state.versionLabel, exact: true })).toBeVisible()
    await page.keyboard.press('Escape')
    await clear(panel, '版本')
    await panel.getByRole('button', { name: '查询', exact: true }).click()
    await expect.poll(() => state.lists.at(-1)).toEqual({ page: '1', page_size: '20' })
    expect(state.unexpected).toEqual([])
  })
}
