import { expect, test, type Page, type Locator } from '@playwright/test'
import { mockCollaboration } from './collaboration-fixture'

async function fixture(page: Page) {
  const unexpected: string[] = []
  const stamp = '2026-11-10T00:00:00Z'
  const version = { id: 1, version_no: 'TEST-ALIGNMENT', name: '按钮对齐验收版本', status: 'DEVELOPING', system_id: 1, system_name: '系统甲', revision: 1, created_at: stamp, updated_at: stamp }
  const req = { id: 1, requirement_no: 'REQ-ALIGNMENT', title: '对齐验收需求', status: 'DONE', priority: 'P2', requirement_type: 'FEATURE', source: 'DIRECT', system_id: 1, description: '只使用合成 API，不写入业务数据', description_format: 'PLAIN', revision: 1, created_at: stamp, updated_at: stamp }
  await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'alignment'); localStorage.setItem('iterflow.refresh_token', 'alignment') })
  await page.route('**/api/v1/**', async route => {
    if (await mockCollaboration(route)) return
    const path = new URL(route.request().url()).pathname
    const data: Record<string, unknown> = {
      '/api/v1/auth/me': { id: 1, username: 'alignment', display_name: '对齐验收', status: 'ACTIVE', revision: 1, permission_codes: ['*'], data_scope: 'ALL', role_ids: [] },
      '/api/v1/notifications/unread-count': { unread_count: 0 },
      '/api/v1/systems': { systems: [{ id: 1, name: '系统甲', enabled: true }], modules: [] },
      '/api/v1/versions': { items: [version], total: 1, page: 1, page_size: 20 },
      '/api/v1/versions/1': version,
      '/api/v1/versions/1/requirements': { items: [req], stats: { total: 1, completed: 1, completion_rate: 1, by_status: { DONE: 1 } } },
      '/api/v1/requirements/1': req, '/api/v1/requirements/1/feedbacks': [],
      '/api/v1/releases': { items: [], total: 0, page: 1, page_size: 20 },
    }
    if (route.request().method() === 'GET' && path in data) return route.fulfill({ json: data[path] })
    unexpected.push(`${route.request().method()} ${path}`)
    return route.fulfill({ status: 500, json: { message: 'unexpected synthetic request' } })
  })
  return unexpected
}
async function rect(locator: Locator) { return locator.evaluate(e => { const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, right: r.right, bottom: r.bottom, width: r.width, height: r.height } }) }
const viewports = [[320, 640], [375, 812], [768, 900], [1024, 768], [1440, 900], [812, 375]]
for (const [width, height] of viewports) {
  for (const entry of ['page', 'drawer']) {
    test(`version actions and filters align in ${entry} ${width}x${height}`, async ({ page }, info) => {
      await page.setViewportSize({ width: width!, height: height! })
      await page.emulateMedia({ reducedMotion: 'reduce' })
      const unexpected = await fixture(page)
      await page.goto(entry === 'page' ? '/#/versions/1' : '/#/versions')
      if (entry === 'drawer') await page.getByText('按钮对齐验收版本', { exact: true }).click()
      const card = page.locator('.section-card').filter({ has: page.getByRole('heading', { name: '需求清单', exact: true }) })
      const batch = card.getByRole('button', { name: '批量处理需求', exact: true })
      const add = card.getByRole('button', { name: '添加需求', exact: true })
      await add.click({ trial: true })
      const a = await rect(batch), b = await rect(add)
      expect.soft(a.height, 'same action group uses equal button height').toBe(b.height)
      expect.soft(Math.abs(a.y - b.y), 'same row actions share their top edge').toBeLessThanOrEqual(1)
      expect.soft(b.x - a.right, 'action spacing is 8px').toBeCloseTo(8, 0)
      const head = await rect(card.locator('.section-card__head'))
      expect.soft(a.x).toBeGreaterThanOrEqual(head.x)
      expect.soft(b.right).toBeLessThanOrEqual(head.right)
      if (width! < 768) expect.soft(a.height, 'mobile touch target').toBeGreaterThanOrEqual(44)
      const controls = card.locator('.worklist-filters .el-input__wrapper, .worklist-filters .el-select__wrapper')
      const reset = card.getByRole('button', { name: '重置清单', exact: true })
      await reset.click({ trial: true })
      const r = await rect(reset)
      for (const control of await controls.all()) {
        const c = await rect(control)
        expect.soft(c.height, 'filter input and action height').toBe(r.height)
        if (width! >= 768) expect.soft(Math.abs(c.bottom - r.bottom), 'filters align to input bottom, excluding labels').toBeLessThanOrEqual(1)
      }
      await card.getByRole('textbox', { name: '清单关键词', exact: true }).fill('不存在的验收项')
      await expect(card.getByText('当前筛选 0 / 1 项可见需求', { exact: true })).toBeVisible()
      await reset.click()
      await expect(card.getByText('当前筛选 1 / 1 项可见需求', { exact: true })).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width!)
      await card.screenshot({ path: info.outputPath('worklist.png') })
      expect(unexpected).toEqual([])
    })
  }
}

test('requirement summary footer aligns its link and button', async ({ page }) => {
  const unexpected = await fixture(page)
  for (const width of [375, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/versions/1')
    await page.getByText('查看', { exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '需求摘要', exact: true })
    const close = dialog.getByRole('button', { name: '关闭', exact: true })
    const link = dialog.getByRole('link', { name: '打开完整详情', exact: true })
    await close.click({ trial: true })
    const a = await rect(close), b = await rect(link)
    expect.soft(Math.abs(a.y + a.height / 2 - b.y - b.height / 2), 'footer control centers').toBeLessThanOrEqual(1)
    expect.soft(b.x - a.right, 'footer gap').toBeCloseTo(8, 0)
    await close.click()
  }
  expect(unexpected).toEqual([])
})
