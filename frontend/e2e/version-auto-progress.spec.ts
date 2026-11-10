import { mockReadPanels } from './collaboration-fixture'
import { expect, test, type Page } from '@playwright/test'

type Options = { status: string; readonly?: boolean; deferredPublish?: boolean }
async function fixture(page: Page, options: Options) {
  const stamp = '2026-11-04T00:00:00Z'
  const version = { id: 1, version_no: 'V-AUTO', name: '需求自动汇总版本', status: options.status, revision: 8, owner_id: 1, description: '只读查看不会推进版本状态', planned_release_date: null, released_at: null, created_at: stamp, updated_at: stamp, updated_by: 1 }
  const req = { id: 7, requirement_no: 'REQ-AUTO', title: '版本中的需求', status: 'DONE', requirement_type: 'FEATURE', source: 'DIRECT', priority: 'P2', owner_id: null, current_version_id: 1, description: '需求验收说明', description_format: 'PLAIN', acceptance_criteria: '检查完整发布门禁', revision: 3, created_at: stamp, updated_at: stamp, updated_by: 1 }
  const writes: { path: string; method: string; body: any }[] = [], unexpected: string[] = [], errors: string[] = []
  let finishCheck!: () => void, finishPublish!: () => void
  const checkGate = new Promise<void>(resolve => { finishCheck = resolve })
  const publishGate = new Promise<void>(resolve => { finishPublish = resolve })
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'auto-progress-local'); localStorage.setItem('iterflow.refresh_token', 'auto-progress-local') })
  await page.route('**/api/v1/**', async route => {
    const method = route.request().method(), path = new URL(route.request().url()).pathname
    const json = (data: unknown, status = 200) => route.fulfill({ status, json: data })
    if (method !== 'GET') writes.push({ path, method, body: route.request().postDataJSON() })
    if (method === 'POST' && path === '/api/v1/versions/1/publish/check') {
      if (options.deferredPublish) {
        await checkGate
        return json({ passed: true, checks: [{ type: 'REQUIREMENTS_DONE', passed: true, message: '关联需求均已完成验收' }] })
      }
      return json({ code: 40923, message: '发布检查未通过', data: { checks: [{ type: 'CONTENT_CONFIRMED', passed: false, message: '当前需求内容需要重新确认', blocking_requirements: [{ id: 7, requirement_no: req.requirement_no, status: req.status }] }] } }, 409)
    }
    if (method === 'POST' && path === '/api/v1/versions/1/publish' && options.deferredPublish) {
      await publishGate
      version.status = 'RELEASED'; version.revision++
      return json({ version_id: 1, release: { id: 4 }, released_requirement_ids: [7], online_feedback_ids: [] })
    }
    const responses: Record<string, unknown> = {
      '/api/v1/auth/me': { id: 1, username: 'progress-local', display_name: '本地合成用户', status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'ALL', role_ids: [], permission_codes: options.readonly ? ['rd.version.view', 'rd.requirement.view'] : ['*'] },
      '/api/v1/me/mail-preferences': { revision: 1, mode: 'TASKS', email: null, pending_email: null, verified: false, smtp_enabled: false, notice_acknowledged: true },
      '/api/v1/notifications/unread-count': { unread_count: 0 }, '/api/v1/systems': { systems: [], modules: [] },
      '/api/v1/versions/1': version,
      '/api/v1/versions/1/requirements': { version_id: 1, items: [req], stats: { total: 1, completed: 1, completion_rate: 1, by_status: { DONE: 1 } } },
      '/api/v1/requirements/7': req,
      '/api/v1/releases': { items: [], total: 0, page: 1, page_size: 20 },
    }
    if (method === 'GET' && path in responses) return json(responses[path])
    if (await mockReadPanels(route)) return
    unexpected.push(`${method} ${path}`)
    return json({ message: 'Unexpected synthetic request' }, 500)
  })
  return { writes, unexpected, errors, finishCheck, finishPublish }
}
const clean = (audit: Awaited<ReturnType<typeof fixture>>) => { expect(audit.errors).toEqual([]); expect(audit.unexpected).toEqual([]) }

for (const width of [375, 1440]) {
  for (const status of ['PLANNING', 'DEVELOPING', 'TESTING', 'READY']) {
    test(`automatic ${status} version explains blockers without manual progress at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      const audit = await fixture(page, { status })
      await page.goto('/#/versions/1')
      const header = page.locator('.page-header')
      await expect(header.getByRole('heading', { name: '需求自动汇总版本', exact: true })).toBeVisible()
      await expect(page.getByText('进度由关联需求自动汇总；开发和验收在需求中完成。', { exact: true })).toBeVisible()
      for (const label of ['开始开发', '提测', '待发布', '退回测试']) await expect(header.getByRole('button', { name: label, exact: true })).toHaveCount(0)
      await expect(header.getByRole('button', { name: '取消版本', exact: true })).toBeVisible()
      await expect(header.getByRole('button')).toHaveCount(3)
      await expect(page.getByRole('button', { name: '添加需求', exact: true })).toBeVisible()
      const memberActions = page.locator(width < 768 ? '.req-card-actions' : '.el-table__body')
      await expect(memberActions.getByText('迁移', { exact: true })).toBeVisible()
      await expect(memberActions.getByText('移出', { exact: true })).toBeVisible()
      await expect(page.locator('.frozen-tip')).toHaveCount(0)
      expect(audit.writes).toEqual([])
      await header.getByRole('button', { name: status === 'READY' ? '发布版本' : '发布检查', exact: true }).click()
      const dialog = page.getByRole('dialog', { name: '发布版本', exact: true })
      await expect(dialog.getByText('当前需求内容需要重新确认', { exact: true })).toBeVisible()
      await dialog.getByRole('textbox', { name: /发布说明/ }).fill('检查阻塞时不能发布')
      await expect(dialog.getByRole('button', { name: '确认发布', exact: true })).toBeDisabled()
      await dialog.getByRole('button', { name: '确认发布', exact: true }).evaluate(button => button.dispatchEvent(new MouseEvent('click', { bubbles: true })))
      await dialog.getByRole('button', { name: '取消', exact: true }).click()
      await expect(dialog).toBeHidden()
      expect(audit.writes.map(write => `${write.method} ${write.path}`)).toEqual(['POST /api/v1/versions/1/publish/check'])
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
      clean(audit)
    })
  }

  for (const status of ['RELEASED', 'CANCELED']) {
    test(`terminal ${status} version freezes requirement membership at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      const audit = await fixture(page, { status })
      await page.goto('/#/versions/1')
      await expect(page.getByRole('heading', { name: '需求自动汇总版本', exact: true })).toBeVisible()
      for (const label of ['发布版本', '发布检查', '取消版本', '添加需求']) await expect(page.getByRole('button', { name: label, exact: true })).toHaveCount(0)
      for (const label of ['迁移', '移出']) await expect(page.getByText(label, { exact: true })).toHaveCount(0)
      await expect(page.locator('.frozen-tip')).toContainText('需求清单已冻结')
      expect(audit.writes).toEqual([])
      clean(audit)
    })
  }

  test(`view permission cannot expose version writes or advance progress at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await fixture(page, { status: 'READY', readonly: true })
    await page.goto('/#/versions/1')
    await expect(page.getByRole('heading', { name: '需求自动汇总版本', exact: true })).toBeVisible()
    await expect(page.locator('.page-header').getByRole('button')).toHaveCount(0)
    await expect(page.getByRole('button', { name: '添加需求', exact: true })).toHaveCount(0)
    await page.locator(width < 768 ? '.req-card-actions' : '.el-table__body').getByText('查看', { exact: true }).click()
    await expect(page.getByRole('dialog', { name: '需求摘要', exact: true })).toContainText('需求验收说明')
    expect(audit.writes).toEqual([])
    clean(audit)
  })

  test(`READY publish waits for passing checks and submits once at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await fixture(page, { status: 'READY', deferredPublish: true })
    await page.goto('/#/versions/1')
    await page.getByRole('button', { name: '发布版本', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '发布版本', exact: true })
    const submit = dialog.getByRole('button', { name: '确认发布', exact: true })
    await dialog.getByRole('textbox', { name: /发布说明/ }).fill('本次验收通过后发布')
    await expect(submit).toBeDisabled()
    expect(audit.writes.filter(write => write.path.endsWith('/publish'))).toHaveLength(0)
    audit.finishCheck()
    await expect(submit).toBeEnabled()
    // Two input events in the same rendering turn must still result in one write.
    await submit.evaluate(button => { button.dispatchEvent(new MouseEvent('click', { bubbles: true })); button.dispatchEvent(new MouseEvent('click', { bubbles: true })) })
    await expect.poll(() => audit.writes.filter(write => write.path.endsWith('/publish')).length).toBe(1)
    audit.finishPublish()
    await expect(dialog).toBeHidden()
    const publishes = audit.writes.filter(write => write.path.endsWith('/publish'))
    expect(publishes).toHaveLength(1)
    expect(publishes[0].body).toMatchObject({ revision: 8, release_notes: '本次验收通过后发布' })
    expect(audit.writes.some(write => write.path.endsWith('/status'))).toBe(false)
    await expect(page.getByRole('button', { name: '发布版本', exact: true })).toHaveCount(0)
    clean(audit)
  })
}
