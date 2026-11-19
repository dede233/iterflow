import { mockReadPanels } from './collaboration-fixture'
import { expect, test, type Locator, type Page } from '@playwright/test'

async function setup(page: Page, entry: 'direct' | 'guided' | 'combined', additionalPeople: { id: number; display_name: string }[] = []) {
  const writes: unknown[] = [], unexpected: string[] = [], errors: string[] = []
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  const requirement = { id: 11, title: '防重复提交需求', requirement_no: 'REQ-11', requirement_type: 'FEATURE', priority: 'P2', status: 'DRAFT', source: 'DIRECT', description: '<p>验证双击只有一次写入</p>', description_format: 'HTML', acceptance_criteria: null, revision: 1, owner_id: null, current_version_id: null, created_at: '2026-11-04T00:00:00Z', updated_at: '2026-11-04T00:00:00Z', updated_by: 1 }
  const feedback = { id: 1, title: '待转需求反馈', feedback_no: 'FB-1', feedback_type: 'OTHER', urgency: 'NORMAL', status: entry === 'guided' ? 'ACCEPTED' : 'NEW', description: '反馈内容转为需求', revision: 1, submitter_id: 1, system_id: null, module_id: null, main_requirement_id: null, created_at: '2026-11-04T00:00:00Z', updated_at: '2026-11-04T00:00:00Z', updated_by: 1 }
  const writePath = {
    direct: '/api/v1/requirements',
    guided: '/api/v1/feedbacks/1/convert',
    combined: '/api/v1/feedbacks/1/accept-and-convert',
  }[entry]
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'issue4-submit'); localStorage.setItem('iterflow.refresh_token', 'issue4-submit') })
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url()), path = url.pathname, method = route.request().method()
    if (method === 'POST' && path === writePath) {
      writes.push(route.request().postDataJSON())
      await pending
      return route.fulfill({ json: requirement })
    }
    if (method === 'GET' && path === '/api/v1/collaboration/people') {
      const keyword = url.searchParams.get('keyword')
      const items = keyword ? additionalPeople.filter(person => person.display_name.includes(keyword)) : [{ id: 1, display_name: '测试成员' }]
      return route.fulfill({ json: { items, total: items.length, page: 1, page_size: 20 } })
    }
    const responses: Record<string, unknown> = {
      '/api/v1/auth/me': { id: 1, username: 'submit-test', display_name: '测试成员', status: 'ACTIVE', must_change_password: false, data_scope: 'ALL', permission_codes: ['*'], can_view_api_docs: false, role_ids: [], revision: 1 },
      '/api/v1/me/mail-preferences': { revision: 1, mode: 'TASKS', email: null, pending_email: null, verified: false, smtp_enabled: false, notice_acknowledged: true },
      '/api/v1/notifications/unread-count': { unread_count: 0 },
      '/api/v1/systems': { systems: [], modules: [] },
      '/api/v1/feedbacks/1': feedback,
      '/api/v1/feedbacks/1/collaboration': { revision: 1, recipients: [{ id: 1, display_name: '测试成员' }], handler_id: null, accepted_by: null, accepted_at: null },
      '/api/v1/feedbacks/1/comments': [],
      '/api/v1/feedbacks/1/attachments': [],
      '/api/v1/requirements/11': requirement,
      '/api/v1/requirements/11/workflow': { revision: 1, content_revision: 1, confirmed_revision: null, needs_confirmation: true, legacy_completed: false, design_status: 'NOT_REQUIRED', paused_from: null, records: [] },
      '/api/v1/requirements/11/participants': { revision: 1, participants: [{ role: 'CONFIRM', user_id: 1, display_name: '测试成员', active: true }] },
      '/api/v1/requirements/11/feedbacks': [],
    }
    if (method !== 'GET' || !(path in responses)) {
      if (await mockReadPanels(route)) return
      unexpected.push(`${method} ${path}`)
      return route.fulfill({ status: 500, json: { message: 'Unexpected request' } })
    }
    return route.fulfill({ json: responses[path] })
  })
  await page.goto(entry === 'direct' ? '/#/requirements/new' : '/#/feedbacks/1')
  return { writes, unexpected, errors, release }
}

for (const width of [375, 1440]) {
  test(`adding a searched developer during creation shows the name and preserves the acceptor at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const developer = { id: 2, display_name: '处理新需求的开发人' }
    const acceptor = { id: 3, display_name: '原验收参与人' }
    const audit = await setup(page, 'direct', [developer, acceptor])
    await page.getByRole('textbox', { name: '*标题', exact: true }).fill('防重复提交需求')
    await page.getByRole('textbox', { name: '需求描述', exact: true }).fill('验证人员安排随需求保存')
    const choose = async (field: Locator, label: string, search = false) => {
      await field.locator('.el-select__wrapper').click()
      const selector = field.getByRole('combobox')
      if (search) await selector.fill(label)
      const listId = await selector.getAttribute('aria-controls')
      await page.locator(`[id="${listId}"]`).getByRole('option', { name: label, exact: true }).click()
      await selector.press('Escape')
    }
    await choose(page.locator('[data-field="confirm"]'), '测试成员')
    await page.getByText('后续人员安排', { exact: false }).click()
    const acceptanceField = page.locator('[data-role="ACCEPT"]')
    await choose(acceptanceField, acceptor.display_name, true)
    await choose(page.locator('[data-role="DEVELOP"]'), developer.display_name, true)

    const add = page.getByRole('button', { name: '将开发人员加入验收', exact: true })
    await add.click()
    await expect(acceptanceField).toContainText(acceptor.display_name)
    await expect(acceptanceField).toContainText(developer.display_name)
    await expect(add).toBeDisabled()
    expect(audit.writes).toEqual([])
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    await page.getByRole('button', { name: '创建', exact: true }).click()
    await expect.poll(() => audit.writes.length).toBe(1)
    expect(audit.writes).toEqual([expect.objectContaining({ participants: [
      { role: 'CONFIRM', user_id: 1 }, { role: 'DEVELOP', user_id: 2 }, { role: 'ACCEPT', user_id: 3 }, { role: 'ACCEPT', user_id: 2 },
    ] })])
    audit.release()
    await expect(page).toHaveURL(/\/#\/requirements\/11$/)
    expect(audit.unexpected).toEqual([])
    expect(audit.errors).toEqual([])
  })

  for (const entry of ['direct', 'guided', 'combined'] as const) {
    test(`${entry} creation sends only once on immediate double click ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      const audit = await setup(page, entry)
      const convert = entry !== 'direct'
      const conversionLabel = entry === 'guided' ? '新建需求' : '受理并转需求'
      const form = convert ? page.getByRole('dialog', { name: conversionLabel, exact: true }) : page.locator('form').filter({ has: page.locator('[data-field="confirm"]') })
      if (convert) {
        await page.getByRole('button', { name: conversionLabel, exact: true }).click()
        await expect(form.getByRole('textbox', { name: '需求描述', exact: true })).toContainText('反馈内容转为需求')
      } else {
        await page.getByRole('textbox', { name: '*标题', exact: true }).fill('防重复提交需求')
        await page.getByRole('textbox', { name: '需求描述', exact: true }).fill('验证双击只有一次写入')
      }
      const button = form.getByRole('button', { name: entry === 'combined' ? '受理并创建需求' : '创建', exact: true })
      if (!convert) {
        const confirmer = form.locator('[data-field="confirm"]')
        await button.click()
        await expect(confirmer).toContainText('请至少选择一名需求确认人')
        expect(audit.writes).toEqual([])
        const selector = confirmer.getByRole('combobox')
        await expect(selector).toBeFocused()
        await confirmer.locator('.el-select__wrapper').click()
        await page.getByRole('option', { name: '测试成员', exact: true }).click()
        await selector.press('Escape')
        await expect(confirmer).not.toContainText('请至少选择一名需求确认人')
      }
      await expect(button).toBeEnabled()
      // Dispatch both clicks in the same task, before Vue renders the loading state.
      // This exercises the synchronous guard, not just Element Plus's disabled button.
      await button.evaluate(node => { (node as HTMLButtonElement).click(); (node as HTMLButtonElement).click() })
      await expect.poll(() => audit.writes.length).toBe(1)
      await expect(button).toHaveClass(/is-loading/)
      expect(audit.writes).toHaveLength(1)
      const body = audit.writes[0] as Record<string, unknown>
      expect(body.description_format).toBe('HTML')
      expect(body.participants).toEqual([{ role: 'CONFIRM', user_id: 1 }])
      if (convert) {
        expect(body.revision).toBe(1)
        expect(body.type).toBe('CREATE_NEW')
        if (entry === 'combined') expect(body.accept_on_convert).toBe(true)
        else expect(body).not.toHaveProperty('accept_on_convert')
        await page.keyboard.press('Escape')
        await expect(form).toBeVisible()
        await expect(form.getByRole('button', { name: '关闭此对话框', exact: true })).toBeHidden()
        await expect(form.getByRole('button', { name: '取消', exact: true })).toBeDisabled()
        await expect(page.getByRole('dialog', { name: '确认关闭？', exact: true })).toBeHidden()
      }
      audit.release()
      await expect(page).toHaveURL(convert ? /\/#\/requirements\/11\?return_to=%2Ffeedbacks$/ : /\/#\/requirements\/11$/)
      await expect(page.getByRole('heading', { name: '防重复提交需求', exact: true })).toBeVisible()
      expect(audit.writes).toHaveLength(1)
      expect(audit.unexpected).toEqual([])
      expect(audit.errors).toEqual([])
    })
  }
}
