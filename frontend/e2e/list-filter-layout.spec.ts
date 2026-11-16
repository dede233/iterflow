import { expect, test, type Locator, type Page } from '@playwright/test'
import { mockCollaboration } from './collaboration-fixture'

async function fixture(page: Page) {
  const unexpected: string[] = []
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'layout-access')
    localStorage.setItem('iterflow.refresh_token', 'layout-refresh')
  })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown) => route.fulfill({ status: 200, json: body })
    if (path === '/api/v1/auth/me') return json({ id: 1, username: 'reader', display_name: '布局查看者', status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'SELF', role_ids: [], permission_codes: ['rd.requirement.view'] })
    if (path === '/api/v1/notifications/unread-count') return json({ unread_count: 0 })
    if (path === '/api/v1/requirements') return json({ items: [], total: 0, page: 1, page_size: 20 })
    if (await mockCollaboration(route)) return
    unexpected.push(`${route.request().method()} ${path}`)
    await route.fulfill({ status: 500, json: { detail: 'unexpected request' } })
  })
  return unexpected
}

async function checkFields(panel: Locator, width: number) {
  const fields = await panel.locator('.el-form-item').evaluateAll(items => items.filter(item => !!item.querySelector('.el-form-item__label')).map(item => {
    const box = (element: Element | Range) => {
      const { x, y, width, height, right, bottom } = element.getBoundingClientRect()
      return { x, y, width, height, right, bottom }
    }
    const label = item.querySelector('.el-form-item__label')!
    const labelText = document.createRange()
    labelText.selectNodeContents(label)
    const control = item.querySelector('.el-select, .el-input-number, .el-date-editor, .el-input')!
    return { name: label.textContent, item: box(item), label: box(label), labelText: box(labelText), control: box(control) }
  }))
  for (const field of fields) {
    expect(field.control.width, `${field.name} has a usable width`).toBeGreaterThanOrEqual(180)
    expect(field.labelText.right, `${field.name} label stays left of its control`).toBeLessThanOrEqual(field.control.x - 8)
    expect(Math.abs(field.label.y + field.label.height / 2 - field.control.y - field.control.height / 2), `${field.name} label is vertically centered`).toBeLessThanOrEqual(2)
    expect(field.control.x, `${field.name} stays in the viewport`).toBeGreaterThanOrEqual(0)
    expect(field.control.right, `${field.name} stays in the viewport`).toBeLessThanOrEqual(width + 1)
  }
  for (let index = 0; index < fields.length; index++) {
    for (const other of fields.slice(index + 1)) {
      const current = fields[index]!
      const gap = Math.max(other.item.x - current.item.right, current.item.x - other.item.right, other.item.y - current.item.bottom, current.item.y - other.item.bottom)
      expect(gap, `${current.name} and ${other.name} remain separated`).toBeGreaterThanOrEqual(8)
    }
  }
  const placeholders = await panel.locator('.el-select__placeholder').evaluateAll(items => items.filter(item => item.textContent?.includes('可搜索')).map(item => ({ text: item.textContent, available: item.clientWidth, needed: item.scrollWidth })))
  for (const placeholder of placeholders) expect(placeholder.needed, `${placeholder.text} is fully visible`).toBeLessThanOrEqual(placeholder.available + 1)
  expect(await panel.page().evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
}

test('requirement advanced filters stay readable and separated', async ({ page }, testInfo) => {
  const width = 1440
  await page.setViewportSize({ width, height: 1000 })
  const unexpected = await fixture(page)
  await page.goto('/#/requirements')
  await expect(page.getByRole('heading', { name: '需求管理', exact: true })).toBeVisible()
  const panel = page.locator('.list-filters')
  await panel.getByRole('button', { name: /^更多筛选/ }).click()
  await expect(panel.locator('.el-form-item__label')).toHaveCount(8)
  await expect(panel.locator('.el-form-item__label').last()).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('advanced-filters.png'), fullPage: true })
  await checkFields(panel, width)
  expect(unexpected).toEqual([])
})
