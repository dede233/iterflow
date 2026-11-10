import { mockReadPanels } from './collaboration-fixture'
import { expect, test, type Page } from '@playwright/test'

async function setup(page: Page, convert: boolean) {
  const writes: unknown[] = [], unexpected: string[] = [], errors: string[] = []
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  const requirement = { id: 11, title: '防重复提交需求', requirement_no: 'REQ-11', requirement_type: 'FEATURE', priority: 'P2', status: 'DRAFT', source: 'DIRECT', description: '<p>验证双击只有一次写入</p>', description_format: 'HTML', acceptance_criteria: null, revision: 1, owner_id: null, current_version_id: null, created_at: '2026-11-04T00:00:00Z', updated_at: '2026-11-04T00:00:00Z', updated_by: 1 }
  const feedback = { id: 1, title: '待转需求反馈', feedback_no: 'FB-1', feedback_type: 'OTHER', urgency: 'NORMAL', status: 'NEW', description: '反馈内容转为需求', revision: 1, submitter_id: 1, system_id: null, module_id: null, main_requirement_id: null, created_at: '2026-11-04T00:00:00Z', updated_at: '2026-11-04T00:00:00Z', updated_by: 1 }
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'issue4-submit'); localStorage.setItem('iterflow.refresh_token', 'issue4-submit') })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname, method = route.request().method()
    if (method === 'POST' && path === (convert ? '/api/v1/feedbacks/1/convert' : '/api/v1/requirements')) {
      writes.push(route.request().postDataJSON())
      await pending
      return route.fulfill({ json: requirement })
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
  await page.goto(convert ? '/#/feedbacks/1' : '/#/requirements/new')
  return { writes, unexpected, errors, release }
}

for (const width of [375, 1440]) {
  for (const convert of [false, true]) {
    test(`${convert ? 'convert feedback' : 'create requirement'} sends only once on immediate double click ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      const audit = await setup(page, convert)
      if (convert) {
        await page.getByRole('button', { name: '转需求', exact: true }).click()
        await expect(page.getByRole('dialog', { name: '转为需求', exact: true }).getByRole('textbox', { name: '需求描述', exact: true })).toContainText('反馈内容转为需求')
      } else {
        await page.getByRole('textbox', { name: '*标题', exact: true }).fill('防重复提交需求')
        await page.getByRole('textbox', { name: '需求描述', exact: true }).fill('验证双击只有一次写入')
      }
      const button = convert
        ? page.getByRole('dialog', { name: '转为需求', exact: true }).getByRole('button', { name: '确定', exact: true })
        : page.getByRole('button', { name: '创建', exact: true })
      await expect(button).toBeEnabled()
      // Dispatch both clicks in the same task, before Vue renders the loading state.
      // This exercises the synchronous guard, not just Element Plus's disabled button.
      await button.evaluate(node => { (node as HTMLButtonElement).click(); (node as HTMLButtonElement).click() })
      await expect.poll(() => audit.writes.length).toBe(1)
      await expect(button).toHaveClass(/is-loading/)
      expect(audit.writes).toHaveLength(1)
      const body = audit.writes[0] as Record<string, unknown>
      expect(body.description_format).toBe('HTML')
      if (convert) { expect(body.revision).toBe(1); expect(body.type).toBe('CREATE_NEW') }
      audit.release()
      await expect(page).toHaveURL(convert ? /\/#\/requirements\/11\?return_to=%2Ffeedbacks$/ : /\/#\/requirements\/11$/)
      await expect(page.getByRole('heading', { name: '防重复提交需求', exact: true })).toBeVisible()
      expect(audit.writes).toHaveLength(1)
      expect(audit.unexpected).toEqual([])
      expect(audit.errors).toEqual([])
    })
  }
}
