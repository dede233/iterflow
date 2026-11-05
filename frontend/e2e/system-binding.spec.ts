import { expect, test, type Page } from '@playwright/test'
import { mockCollaboration } from './collaboration-fixture'

async function fixture(page: Page) {
  const stamp = '2026-11-05T00:00:00Z'
  const req = { id: 1, requirement_no: 'REQ-BINDING', title: '补齐业务系统的历史需求', description: '完整需求内容', description_format: 'PLAIN', status: 'DRAFT', requirement_type: 'FEATURE', source: 'DIRECT', priority: 'P2', revision: 1, system_id: null as number | null, system_name: null as string | null, module_id: null, current_version_id: null as number | null, acceptance_criteria: '', created_at: stamp, updated_at: stamp }
  const version = { id: 2, version_no: 'V-BIND', name: '同系统版本', revision: 1, status: 'PLANNING', system_id: null as number | null, system_name: null as string | null, planned_release_date: null, released_at: null, description: '', owner_id: 1, created_at: stamp, updated_at: stamp }
  const writes: { path: string; body: any }[] = [], queries: { path: string; system: string | null }[] = [], unexpected: string[] = []
  await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'binding-local'); localStorage.setItem('iterflow.refresh_token', 'binding-local') })
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url()), path = url.pathname, method = route.request().method()
    const reply = (json: unknown, status = 200) => route.fulfill({ status, json })
    if (path === '/api/v1/systems/options') return reply([{ id: 1, name: '系统甲' }, { id: 2, name: '系统乙' }])
    if (path === '/api/v1/auth/me') return reply({ id: 1, username: 'binding', display_name: '测试用户', status: 'ACTIVE', must_change_password: false, permission_codes: ['*'], data_scope: 'ALL', role_ids: [] })
    if (path === '/api/v1/notifications/unread-count') return reply({ unread_count: 0 })
    if (path === '/api/v1/me/mail-preferences') return reply({ revision: 1, mode: 'TASKS', verified: false, email: null, smtp_enabled: false, notice_acknowledged: true })
    if (method === 'POST' && /\/editing\//.test(path)) return reply({ editors: [] })
    if (path === '/api/v1/requirements/1' && method === 'PATCH') {
      const body = route.request().postDataJSON(); writes.push({ path, body })
      Object.assign(req, body, { revision: req.revision + 1, system_name: body.system_id === 1 ? '系统甲' : '系统乙' })
      return reply(req)
    }
    if (path === '/api/v1/versions' && method === 'POST') {
      const body = route.request().postDataJSON(); writes.push({ path, body })
      expect(body.system_id).toBe(1)
      Object.assign(version, body, { system_name: '系统甲' })
      if (body.requirement_id) req.current_version_id = 2
      return reply(version)
    }
    if (path === '/api/v1/requirements/1') return reply(req)
    if (path === '/api/v1/requirements/1/feedbacks') return reply([])
    if (path === '/api/v1/versions/2') return reply(version)
    if (path === '/api/v1/versions/2/requirements') return reply({ version_id: 2, items: req.current_version_id ? [req] : [], stats: { total: req.current_version_id ? 1 : 0, completed: 0, completion_rate: 0, by_status: {} } })
    if (path === '/api/v1/releases') return reply({ items: [], total: 0, page: 1, page_size: 20 })
    if (path === '/api/v1/requirements' || path === '/api/v1/versions') {
      queries.push({ path, system: url.searchParams.get('system_id') })
      const item = path.endsWith('requirements') ? req : version
      const items = !url.searchParams.get('system_id') || Number(url.searchParams.get('system_id')) === item.system_id ? [item] : []
      return reply({ items, total: items.length, page: 1, page_size: 20 })
    }
    if (await mockCollaboration(route)) return
    unexpected.push(`${method} ${path}`); return reply({ message: 'Unexpected request' }, 500)
  })
  return { req, version, writes, queries, unexpected }
}

for (const width of [1440, 375]) {
  test(`legacy requirement gets a system and creates a same-system version at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await fixture(page)
    await page.goto('/#/requirements/1')
    await page.getByRole('button', { name: '创建版本', exact: true }).click()
    const creation = page.getByRole('dialog', { name: '创建版本并关联需求', exact: true })
    await expect(creation.getByRole('alert')).toContainText('未指定业务系统')
    await creation.getByRole('button', { name: '取消', exact: true }).click()
    await page.getByRole('button', { name: '编辑', exact: true }).click()
    const editor = page.getByRole('dialog', { name: '编辑需求', exact: true })
    await editor.locator('.el-form-item').filter({ hasText: '业务系统' }).locator('.el-select').click()
    await page.getByRole('option', { name: '系统甲', exact: true }).click()
    await editor.getByRole('button', { name: '保存', exact: true }).click()
    await expect(editor).toBeHidden()
    await expect(page.getByText('系统甲', { exact: true })).toBeVisible()
    expect(audit.writes[0].body).toMatchObject({ system_id: 1, module_id: null, revision: 1 })
    await page.getByRole('button', { name: '创建版本', exact: true }).click()
    await creation.getByRole('textbox', { name: /版本号/ }).fill('V-BIND')
    await expect(creation.getByRole('combobox', { name: /业务系统/ })).toBeDisabled()
    await creation.getByRole('button', { name: '创建并关联', exact: true }).click()
    await expect(creation).toBeHidden()
    expect(audit.writes[1].body).toMatchObject({ system_id: 1, requirement_id: 1, requirement_revision: 2 })
    await expect(page.getByRole('heading', { name: audit.version.name, exact: true })).toBeVisible()
    expect(audit.unexpected).toEqual([])
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await page.screenshot({ path: `test-results/system-binding-version-${width}.png`, fullPage: true })
  })

  test(`version creation requires system selection and filters persist at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await fixture(page)
    await page.goto('/#/versions/new')
    await page.getByRole('textbox', { name: /版本号/ }).fill('V-NEW')
    await page.getByRole('textbox', { name: /版本名称/ }).fill('系统甲新版本')
    await page.getByRole('button', { name: '创建', exact: true }).click()
    await expect(page.getByText('请选择业务系统', { exact: true })).toBeVisible()
    expect(audit.writes).toHaveLength(0)
    await page.locator('.el-form-item').filter({ hasText: '业务系统' }).locator('.el-select').click()
    await page.getByRole('option', { name: '系统甲', exact: true }).click()
    await page.getByRole('button', { name: '创建', exact: true }).click()
    await expect(page.getByRole('heading', { name: '系统甲新版本', exact: true })).toBeVisible()
    await page.goto('/#/versions?system_id=1')
    await expect.poll(() => audit.queries.some(query => query.path.endsWith('versions') && query.system === '1')).toBe(true)
    await page.reload()
    await expect(page.getByText('系统甲新版本', { exact: true })).toBeVisible()
    await page.goto('/#/requirements?system_id=2')
    await expect.poll(() => audit.queries.some(query => query.path.endsWith('requirements') && query.system === '2')).toBe(true)
    expect(audit.unexpected).toEqual([])
  })
}
