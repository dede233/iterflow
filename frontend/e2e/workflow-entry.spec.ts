import { expect, test, type Page } from '@playwright/test'

async function setup(page: Page, options: any = {}) {
  const { status = 'DEVELOPING', actor = 1, administrator = true, participants: initialPeople = ['CONFIRM', 'DESIGN', 'DEVELOP', 'ACCEPT'].map(role => ({ role, user_id: 1, display_name: '环节人员', active: true })), design = 'NOT_REQUIRED', confirmed: initialConfirmed = true, feedback = false, editable = true, reject = false } = options
  let participants = initialPeople, confirmed = initialConfirmed, designStatus = design
  const item = { id: 1, requirement_no: 'REQ-ENTRY', title: '流程入口回归', requirement_type: 'FEATURE', source: 'DIRECT', priority: 'P1', status, owner_id: null, current_version_id: null, description: '检查人员与状态操作衔接', acceptance_criteria: '人员保存不自动流转', revision: 8, created_at: '2026-11-03T00:00:00Z', updated_at: '2026-11-03T00:00:00Z', updated_by: 1 }
  const writes: any[] = [], unexpected: string[] = [], errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'local-entry'); localStorage.setItem('iterflow.refresh_token', 'local-entry') })
  const flow = () => ({ revision: item.revision, content_revision: 2, confirmed_revision: confirmed ? 2 : 1, needs_confirmation: !confirmed, legacy_completed: false, design_status: designStatus, paused_from: status === 'PAUSED' ? 'DEVELOPING' : null, records: [] })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname, method = route.request().method()
    const body = method === 'GET' ? null : route.request().postDataJSON()
    if (method === 'PUT' && path === '/api/v1/requirements/1/participants') {
      expect(body.revision).toBe(item.revision); writes.push(body)
      participants = body.participants.map((p: any) => ({ ...p, display_name: p.user_id === 2 ? '验收小李' : '环节人员', active: true })); item.revision++
      return route.fulfill({ json: { revision: item.revision, participants } })
    }
    if (method === 'POST' && path === '/api/v1/requirements/1/workflow') {
      expect(body.revision).toBe(item.revision); writes.push(body)
      if (body.action === 'CONFIRM') confirmed = true
      else if (body.action === 'DESIGN_DONE') designStatus = 'DONE'
      else throw new Error(`Unexpected workflow ${body.action}`)
      item.revision++
      return route.fulfill({ json: flow() })
    }
    if (method === 'PATCH' && /\/(requirements|feedbacks)\/1\/status$/.test(path)) {
      expect(body.revision).toBe(item.revision); writes.push(body)
      if (reject) return route.fulfill({ status: 403, json: { code: 40301, message: '环节人员已调整，请刷新后由对应人员操作', data: null } })
      if (actor !== 1) expect(body.reason?.trim().length).toBeGreaterThan(0)
      item.status = body.status; item.revision++
      return route.fulfill({ json: feedback ? { ...item, feedback_no: 'FB-ENTRY', feedback_type: 'BUG', urgency: 'NORMAL', submitter_id: 2, main_requirement_id: null } : item })
    }
    const permission_codes = editable ? ['*'] : ['rd.requirement.view', 'rd.requirement.status', 'rd.feedback.view', 'rd.feedback.edit']
    const responses: Record<string, unknown> = {
      '/api/v1/auth/me': { id: actor, username: 'entry-test', display_name: '回归账号', status: 'ACTIVE', must_change_password: false, data_scope: 'ALL', permission_codes, can_view_api_docs: administrator, role_ids: [], revision: 1 },
      '/api/v1/me/mail-preferences': { revision: 1, mode: 'TASKS', email: null, pending_email: null, verified: false, smtp_enabled: false, notice_acknowledged: false },
      '/api/v1/notifications/unread-count': { unread_count: 0 }, '/api/v1/systems': { systems: [], modules: [] },
      '/api/v1/requirements/1': item, '/api/v1/requirements/1/workflow': flow(),
      '/api/v1/requirements/1/participants': { revision: item.revision, participants }, '/api/v1/requirements/1/feedbacks': [],
      '/api/v1/collaboration/people': { items: [{ id: 1, display_name: '环节人员' }, { id: 2, display_name: '验收小李' }], total: 2, page: 1, page_size: 20 },
      '/api/v1/feedbacks/1': { ...item, feedback_no: 'FB-ENTRY', feedback_type: 'BUG', urgency: 'NORMAL', submitter_id: 2, main_requirement_id: null },
      '/api/v1/feedbacks/1/attachments': [], '/api/v1/feedbacks/1/comments': [],
      '/api/v1/feedbacks/1/collaboration': { revision: item.revision, recipients: options.legacy ? [] : [{ id: 1, display_name: '指定接收人' }], handler_id: null, accepted_by: null, accepted_at: null },
    }
    if (method !== 'GET' || !(path in responses)) { unexpected.push(`${method} ${path}`); return route.fulfill({ status: 500, json: { message: 'Unexpected request' } }) }
    return route.fulfill({ json: responses[path] })
  })
  await page.goto(feedback ? '/#/feedbacks/1' : '/#/requirements/1')
  if (!feedback) await page.getByRole('button', { name: '展开需求进度', exact: true }).click()
  return { writes, unexpected, errors }
}
function clean(audit: Awaited<ReturnType<typeof setup>>) { expect(audit.unexpected).toEqual([]); expect(audit.errors).toEqual([]) }

for (const width of [375, 1440]) {
  test(`assign missing acceptor before submission at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await setup(page, { participants: [{ role: 'DEVELOP', user_id: 1, display_name: '环节人员', active: true }] })
    await expect(page.getByRole('button', { name: '提交验收', exact: true })).toBeDisabled()
    await page.getByRole('button', { name: '设置验收人员', exact: true }).click()
    const people = page.getByRole('dialog', { name: '设置验收人员', exact: true })
    await people.locator('.el-select__wrapper').click()
    const listId = await people.getByRole('combobox').getAttribute('aria-controls')
    await page.locator(`[id="${listId}"]`).getByRole('option', { name: '验收小李', exact: true }).click()
    await people.getByRole('combobox').press('Escape')
    await people.getByRole('button', { name: '保存人员', exact: true }).click()
    await expect(people).toBeHidden()
    await expect(page.getByRole('button', { name: '提交验收', exact: true })).toBeEnabled()
    expect(audit.writes).toHaveLength(1)
    expect(audit.writes[0].participants).toEqual([{ role: 'DEVELOP', user_id: 1 }, { role: 'ACCEPT', user_id: 2 }])
    await page.screenshot({ path: info.outputPath('assigned-before-submission.png'), fullPage: true })
    clean(audit)
  })
  for (const missing of ['DEVELOP', 'ACCEPT']) {
    test(`explain missing ${missing} without edit permission at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      const audit = await setup(page, { status: missing === 'DEVELOP' ? 'CONFIRMED' : 'TESTING', participants: [], editable: false })
      await expect(page.getByText(/尚未设置有效的.*请联系有人员编辑权限的成员完成设置/).first()).toBeVisible()
      await expect(page.getByRole('button', { name: /设置开发人员|设置验收人员/ })).toHaveCount(0)
      expect(audit.writes).toEqual([]); clean(audit)
    })
  }
  for (const mode of ['design', 'confirmation']) {
    test(`resolve ${mode} before submission at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      const audit = await setup(page, mode === 'design' ? { design: 'IN_PROGRESS' } : { confirmed: false })
      await expect(page.getByRole('button', { name: '提交验收', exact: true })).toBeDisabled()
      await page.getByRole('button', { name: mode === 'design' ? '完成设计' : '确认当前内容', exact: true }).click()
      const dialog = page.getByRole('dialog', { name: mode === 'design' ? '完成设计' : '确认当前内容', exact: true })
      await dialog.getByRole('button', { name: '确认操作', exact: true }).click()
      await expect(dialog).toBeHidden()
      await expect(page.getByRole('button', { name: '提交验收', exact: true })).toBeEnabled()
      expect(audit.writes).toHaveLength(1); clean(audit)
    })
  }
  for (const [status, action] of [['CONFIRMED', '开始开发'], ['DEVELOPING', '提交验收'], ['TESTING', '验收通过'], ['TESTING', '退回开发'], ['DONE', '重新开发'], ['PAUSED', '恢复开发']]) {
    test(`require delegated ${action} reason before request at ${width}px`, async ({ page }, info) => {
      await page.setViewportSize({ width, height: 900 })
      const audit = await setup(page, { status, actor: 9 })
      await page.getByRole('button', { name: action, exact: true }).click()
      const dialog = page.getByRole('dialog', { name: action, exact: true })
      await expect(dialog.getByText('代操作原因（必填）', { exact: true })).toBeVisible()
      await dialog.getByRole('button', { name: '确定', exact: true }).click()
      expect(audit.writes).toHaveLength(0)
      await dialog.getByRole('textbox').fill('经指定人员授权代操作')
      await page.screenshot({ path: info.outputPath('delegated-reason.png'), fullPage: true })
      await dialog.getByRole('button', { name: '确定', exact: true }).click()
      await expect(dialog).toBeHidden()
      expect(audit.writes).toHaveLength(1)
      expect(audit.writes[0].reason).toBe('经指定人员授权代操作'); clean(audit)
    })
  }
  test(`allow delegated feedback acceptance with reason at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await setup(page, { feedback: true, status: 'NEW', actor: 9 })
    await page.getByRole('button', { name: '受理', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '受理', exact: true })
    await expect(dialog.getByRole('textbox', { name: /代受理原因（必填）/ })).toBeVisible()
    await dialog.getByRole('button', { name: '确定', exact: true }).click()
    expect(audit.writes).toHaveLength(0)
    await dialog.getByRole('textbox').fill('接收人授权代受理')
    await dialog.getByRole('button', { name: '确定', exact: true }).click()
    await expect(dialog).toBeHidden()
    expect(audit.writes[0].reason).toBe('接收人授权代受理'); clean(audit)
  })
  test(`hide acceptance for ordinary non-receiver at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await setup(page, { feedback: true, status: 'NEW', actor: 9, administrator: false })
    await expect(page.getByText(/请联系指定接收人受理此反馈/)).toBeVisible()
    await expect(page.getByRole('button', { name: '受理', exact: true })).toHaveCount(0)
    expect(audit.writes).toEqual([]); clean(audit)
  })
  for (const legacy of [false, true]) {
    test(`retain ordinary feedback acceptance legacy=${legacy} at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      const audit = await setup(page, { feedback: true, status: 'NEW', actor: 1, administrator: false, legacy })
      await page.getByRole('button', { name: '受理', exact: true }).click()
      const dialog = page.getByRole('dialog', { name: '受理', exact: true })
      await expect(dialog.getByRole('textbox')).toHaveCount(0)
      await dialog.getByRole('button', { name: '确定', exact: true }).click()
      await expect(dialog).toBeHidden()
      expect(audit.writes[0].reason).toBeNull(); clean(audit)
    })
  }
  test(`preserve exact server refusal and input without replay at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await setup(page, { status: 'TESTING', actor: 9, reject: true })
    await page.getByRole('button', { name: '验收通过', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '验收通过', exact: true })
    await dialog.getByRole('textbox').fill('已取得指定人员授权')
    await dialog.getByRole('button', { name: '确定', exact: true }).click()
    await expect(dialog.getByRole('alert')).toHaveText('环节人员已调整，请刷新后由对应人员操作')
    await expect(dialog.getByRole('textbox')).toHaveValue('已取得指定人员授权')
    await expect(page.getByText('你没有权限执行该操作', { exact: true })).toHaveCount(0)
    expect(audit.writes).toHaveLength(1); clean(audit)
  })
}
