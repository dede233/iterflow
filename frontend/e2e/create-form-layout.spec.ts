import { expect, test, type Page } from '@playwright/test'
import { mockCollaboration } from './collaboration-fixture'

async function fixture(page: Page) {
  const unexpected: string[] = []
  await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'layout-test'); localStorage.setItem('iterflow.refresh_token', 'layout-refresh') })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (await mockCollaboration(route)) return
    const requirement = { id: 1, requirement_no: 'REQ-LAYOUT', title: '弹窗布局验收', description: '仅本地合成数据', description_format: 'PLAIN', requirement_type: 'FEATURE', priority: 'P2', source: 'DIRECT', status: 'DRAFT', system_id: 1, system_name: '系统甲', current_version_id: null, revision: 1 }
    const data: Record<string, unknown> = {
      '/api/v1/auth/me': { id: 1, username: 'layout', display_name: '布局测试', status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'ALL', permission_codes: ['*'], role_ids: [] },
      '/api/v1/notifications/unread-count': { unread_count: 0 },
      '/api/v1/systems': { systems: [{ id: 1, name: '系统甲', enabled: true }], modules: [] },
      '/api/v1/requirements': { items: [requirement], total: 1, page: 1, page_size: 20 },
      '/api/v1/feedbacks': { items: [], total: 0, page: 1, page_size: 20 },
      '/api/v1/versions': { items: [], total: 0, page: 1, page_size: 20 },
      '/api/v1/requirements/1': requirement,
      '/api/v1/requirements/1/feedbacks': [],
      '/api/v1/collaboration/people': { items: [{ id: 1, display_name: '布局测试' }], total: 1, page: 1, page_size: 20 },
    }
    if (route.request().method() === 'GET' && path in data) return route.fulfill({ json: data[path] })
    unexpected.push(`${route.request().method()} ${path}`)
    return route.fulfill({ status: 500, json: { message: 'unexpected request' } })
  })
  return unexpected
}
const entries = [
  { path: '/requirements', button: '新建需求', title: '新建需求' },
  { path: '/feedbacks', button: '提交反馈', title: '提交反馈' },
  { path: '/versions', button: '新建版本', title: '新建版本' },
  { path: '/requirements/1', button: '创建版本', title: '创建版本并关联需求' },
]
for (const [width, height] of [[320, 640], [375, 812], [768, 600], [1440, 900], [1440, 480]]) {
  for (const entry of entries) {
    test(`${entry.title} has separate scrolling content and reachable actions ${width}x${height}`, async ({ page }, info) => {
      await page.setViewportSize({ width: width!, height: height! })
      const unexpected = await fixture(page)
      await page.goto('/#' + entry.path)
      await page.getByRole('button', { name: entry.button, exact: true }).click()
      const dialog = page.getByRole('dialog', { name: entry.title, exact: true })
      const fields = dialog.locator('.create-form-fields')
      const footer = dialog.locator('.editor-actions, .form-actions')
      await expect(footer.getByRole('button', { name: '取消', exact: true })).toBeVisible()
      if (entry.title === '新建需求') {
        await dialog.locator('.optional-people summary').click()
        await expect(dialog.locator('.optional-people')).toHaveAttribute('open', '')
      }
      await footer.getByRole('button', { name: '取消', exact: true }).click({ trial: true })
      const footerY = (await footer.boundingBox())!.y
      for (const fraction of [0, 0.5, 1]) {
        await fields.evaluate((element, fraction) => { element.scrollTop = (element.scrollHeight - element.clientHeight) * fraction }, fraction)
        const geometry = await dialog.evaluate(element => {
          const fields = element.querySelector('.create-form-fields')!.getBoundingClientRect()
          const footer = element.querySelector('.editor-actions, .form-actions')!.getBoundingClientRect()
          const body = element.querySelector('.el-dialog__body')!
          const rect = element.getBoundingClientRect()
          return { fieldBottom: fields.bottom, footerTop: footer.top, footerBottom: footer.bottom, dialogTop: rect.top, dialogBottom: rect.bottom, bodyOverflow: body.scrollHeight - body.clientHeight, pageOverflow: document.documentElement.scrollWidth - innerWidth }
        })
        expect(geometry.fieldBottom).toBeLessThanOrEqual(geometry.footerTop + 1)
        expect(Math.abs(geometry.footerTop - footerY)).toBeLessThan(1)
        expect(geometry.dialogTop).toBeGreaterThanOrEqual(0)
        expect(geometry.dialogBottom).toBeLessThanOrEqual(height! + 1)
        expect(geometry.bodyOverflow).toBeLessThanOrEqual(1)
        expect(geometry.pageOverflow).toBeLessThanOrEqual(1)
        const cancel = footer.getByRole('button', { name: '取消', exact: true })
        await cancel.click({ trial: true })
      }
      const lastControl = fields.locator('input:not([type="hidden"]):visible, textarea:visible, button:visible').last()
      await lastControl.focus()
      await expect(lastControl).toBeInViewport()
      const control = (await lastControl.boundingBox())!
      expect(control.y + control.height).toBeLessThanOrEqual((await footer.boundingBox())!.y + 1)
      await page.screenshot({ path: info.outputPath('form-bottom.png') })
      await footer.getByRole('button', { name: '取消', exact: true }).click()
      await expect(dialog).toBeHidden()
      expect(unexpected).toEqual([])
    })
  }
}

test('scrolled requirement people selector remains clickable above the footer', async ({ page }, info) => {
  await page.setViewportSize({ width: 375, height: 640 })
  const unexpected = await fixture(page)
  await page.goto('/#/requirements')
  await page.getByRole('button', { name: '新建需求', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '新建需求', exact: true })
  await dialog.locator('.optional-people summary').click()
  const selector = dialog.locator('.optional-people .el-select').last()
  await selector.locator('.el-select__wrapper').click()
  const list = await selector.getByRole('combobox').getAttribute('aria-controls')
  await page.locator(`[id="${list}"]`).getByRole('option', { name: '布局测试', exact: true }).click()
  await selector.getByRole('combobox').press('Escape')
  await expect(selector).toContainText('布局测试')
  await page.screenshot({ path: info.outputPath('selected-person.png') })
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(dialog).toBeHidden()
  expect(unexpected).toEqual([])
})
