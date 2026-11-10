import { expect, test, type Page } from '@playwright/test'
import { mockCollaboration } from './collaboration-fixture'

async function fixture(page: Page) {
  const stamp = '2026-11-10T00:00:00Z'
  const feedback = { id: 1, feedback_no: 'FB-OLD-MODULE', title: '保留历史模块的反馈', feedback_type: 'OTHER', urgency: 'NORMAL', status: 'NEW', system_id: 1, system_name: '系统甲', module_id: 2, module_name: '已停用旧模块', submitter_id: 1, description: '反馈内容', revision: 1, created_at: stamp, updated_at: stamp }
  const writes: any[] = [], queries: URLSearchParams[] = [], errors: string[] = [], unexpected: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'module-test'); localStorage.setItem('iterflow.refresh_token', 'module-test') })
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url()), path = url.pathname, method = route.request().method()
    const reply = (json: unknown, status = 200) => route.fulfill({ status, json })
    if (await mockCollaboration(route)) return
    if (path === '/api/v1/auth/me') return reply({ id: 1, username: 'module-test', display_name: '验收用户', status: 'ACTIVE', must_change_password: false, data_scope: 'ALL', permission_codes: ['*'], role_ids: [] })
    if (path === '/api/v1/notifications/unread-count') return reply({ unread_count: 0 })
    if (path === '/api/v1/systems') return reply({ systems: [{ id: 1, name: '系统甲', enabled: true }, { id: 3, name: '系统乙', enabled: true }], modules: [{ id: 2, system_id: 1, name: '已停用旧模块', enabled: false }, { id: 4, system_id: 1, name: '仍启用旧模块', enabled: true }] })
    if (path === '/api/v1/collaboration/people') return reply({ items: [{ id: 1, display_name: '验收用户' }], total: 1, page: 1, page_size: 20 })
    if (path === '/api/v1/feedbacks') {
      if (method === 'GET') { queries.push(url.searchParams); return reply({ items: [feedback], total: 1, page: 1, page_size: 20 }) }
      const body = route.request().postDataJSON(); writes.push(body); return reply({ ...feedback, ...body }, 201)
    }
    if (path === '/api/v1/feedbacks/1') {
      if (method === 'PATCH') { const body = route.request().postDataJSON(); writes.push(body); Object.assign(feedback, body, { revision: feedback.revision + 1 }) }
      return reply(feedback)
    }
    if (path.endsWith('/attachments') || path.endsWith('/comments')) return reply([])
    if (path.startsWith('/api/v1/editing/')) return reply({ ok: true, existing_editor: null })
    unexpected.push(`${method} ${path}`); return reply({}, 500)
  })
  return { feedback, writes, queries, errors, unexpected }
}

for (const width of [1440, 375]) {
  test(`feedback list, detail and legacy edits omit modules at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 1000 })
    const data = await fixture(page)
    await page.goto('/#/feedbacks?system_id=1&module_id=2')
    await expect(page.getByText('保留历史模块的反馈', { exact: true }).first()).toBeVisible()
    expect(data.queries.length).toBeGreaterThan(0)
    expect(data.queries.every(q => q.get('system_id') === '1' && !q.has('module_id'))).toBe(true)
    if (width < 768) await page.getByRole('button', { name: '筛选', exact: true }).click()
    await expect(page.locator('.el-form-item').filter({ hasText: /^模块/ })).toHaveCount(0)
    await page.getByRole('button', { name: '查询', exact: true }).click()
    await expect(page).not.toHaveURL(/module_id/)
    await page.goto('/#/feedbacks/1')
    await expect(page.getByRole('heading', { name: '保留历史模块的反馈', exact: true })).toBeVisible()
    await expect(page.getByText('所属模块', { exact: true })).toHaveCount(0)
    await expect(page.getByText('已停用旧模块', { exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: '编辑', exact: true }).click()
    const edit = page.getByRole('dialog', { name: '编辑反馈', exact: true })
    await expect(edit.getByText('所属模块', { exact: true })).toHaveCount(0)
    await edit.getByRole('textbox', { name: '标题', exact: true }).fill('修改内容保留旧模块')
    await edit.getByRole('button', { name: '保存', exact: true }).click()
    await expect(edit).toBeHidden()
    expect(data.writes[0]).not.toHaveProperty('system_id'); expect(data.writes[0]).not.toHaveProperty('module_id')
    expect(data.feedback.module_id).toBe(2)
    await page.getByRole('button', { name: '编辑', exact: true }).click()
    await edit.locator('.el-form-item').filter({ hasText: '所属系统' }).locator('.el-select').click()
    await page.getByRole('option', { name: '系统乙', exact: true }).click()
    await page.screenshot({ path: info.outputPath('edit-system.png'), fullPage: true })
    await edit.getByRole('button', { name: '保存', exact: true }).click()
    await expect(edit).toBeHidden()
    expect(data.writes[1]).toMatchObject({ system_id: 3, module_id: null, revision: 2 })
    expect(data.errors).toEqual([]); expect(data.unexpected).toEqual([])
  })
  for (const embedded of [false, true]) test(`feedback creation has system only at ${width}px embedded=${embedded}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 1000 })
    const data = await fixture(page)
    await page.goto(embedded ? '/#/feedbacks' : '/#/feedbacks/new')
    if (embedded) await page.getByRole('button', { name: '提交反馈', exact: true }).click()
    const form = embedded ? page.getByRole('dialog', { name: '提交反馈', exact: true }) : page.locator('main')
    await form.getByRole('textbox', { name: /标题$/ }).fill('不选择模块的新反馈')
    await form.getByRole('textbox', { name: /详细描述$/ }).fill('只选择业务系统并提交')
    const system = form.locator('.el-form-item').filter({ hasText: '所属系统' })
    await system.locator('.el-select').click()
    await page.getByRole('option', { name: '系统甲', exact: true }).click()
    await expect(form.getByText('所属模块', { exact: true })).toHaveCount(0)
    const grid = await form.locator('.form-grid').boundingBox(), field = await system.boundingBox()
    expect(Math.abs(grid!.width - field!.width)).toBeLessThan(2)
    await form.locator('.el-form-item').filter({ hasText: '反馈接收人' }).locator('.el-select').click()
    await page.getByRole('option', { name: /验收用户/ }).click()
    await page.keyboard.press('Escape')
    await page.screenshot({ path: info.outputPath('create-system-only.png'), fullPage: true })
    await form.getByRole('button', { name: '提交', exact: true }).click()
    await expect.poll(() => data.writes.length).toBe(1)
    expect(data.writes[0]).toMatchObject({ system_id: 1, recipient_ids: [1] })
    expect(data.writes[0]).not.toHaveProperty('module_id')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    expect(data.errors).toEqual([]); expect(data.unexpected).toEqual([])
  })
}
