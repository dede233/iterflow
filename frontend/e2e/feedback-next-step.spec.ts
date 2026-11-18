import { expect, test, type Locator, type Page } from '@playwright/test'
import type { ConvertFeedbackPayload, Feedback, FeedbackStatusChangePayload, Requirement } from '../src/types/domain'
import { mockReadPanels } from './collaboration-fixture'

const timestamp = '2026-11-18T00:00:00Z'
const title = '已受理后明确反馈处理方向'
const description = '提交人提供的具体内容\n第二行保留原始语义'
const draftTitle = '暂未保存的需求标题'
const draftDescription = '在反馈详情中补充需求内容'
const systems = [{ id: 1, name: '系统甲' }, { id: 2, name: '系统乙' }]

async function fixture(page: Page, status: Feedback['status'], {
  unbound = false, permissionCodes = ['*'], systemConflict = false,
} = {}) {
  const feedback: Feedback = {
    id: 1, feedback_no: 'FB-NEXT', title, feedback_type: 'OTHER', urgency: 'NORMAL',
    status, description, submitter_id: 1, submitter_display_name: '指定接收人', system_id: unbound ? null : 1, system_name: unbound ? null : '系统甲', module_id: null,
    expected_result: null, actual_result: null, reproduce_steps: null, main_requirement_id: null, duplicate_of_id: null,
    revision: 4, created_at: timestamp, updated_at: timestamp, updated_by: 1,
  }
  const other: Feedback = { ...feedback, id: 2, feedback_no: 'FB-OTHER', title: '另一条重复反馈', status: 'DUPLICATE', duplicate_of_id: feedback.id }
  let requirement: Requirement | undefined
  const statusWrites: FeedbackStatusChangePayload[] = []
  const conversions: ConvertFeedbackPayload[] = []
  const requests: string[] = []
  const unexpected: string[] = []
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'feedback-next-step-mock')
    localStorage.setItem('iterflow.refresh_token', 'feedback-next-step-mock')
  })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname.slice('/api/v1'.length)
    const method = route.request().method()
    requests.push(`${method} ${path}`)
    const json = (body: unknown, responseStatus = 200) => route.fulfill({ status: responseStatus, json: body })
    if (method === 'GET' && path === '/systems/options') return json(systems)
    if (await mockReadPanels(route)) return
    if (method === 'PATCH' && path === '/feedbacks/1/status') {
      const payload: FeedbackStatusChangePayload = route.request().postDataJSON()
      statusWrites.push(payload)
      feedback.status = payload.status
      feedback.revision += 1
      return json(feedback)
    }
    if (method === 'POST' && path === '/feedbacks/1/convert') {
      const payload: ConvertFeedbackPayload = route.request().postDataJSON()
      conversions.push(payload)
      if (systemConflict && conversions.length === 1) {
        Object.assign(feedback, { system_id: 1, system_name: '系统甲', revision: feedback.revision + 1 })
        return json({ code: 40910, message: '服务器版本发生变更', data: { current_revision: feedback.revision, current_updated_at: timestamp, current_updated_by: 2 } }, 409)
      }
      const system = systems.find(({ id }) => id === (feedback.system_id ?? payload.system_id))
      requirement = {
        id: 7, requirement_no: 'REQ-NEXT', title: payload.requirement_title!, requirement_type: payload.requirement_type!,
        status: 'DRAFT', priority: payload.priority!, source: 'FEEDBACK', description: payload.description!, description_format: 'HTML',
        system_id: system?.id ?? null, system_name: system?.name ?? null, module_id: null, owner_id: null, release_frozen: false,
        current_version_id: null, acceptance_criteria: payload.acceptance_criteria ?? null, revision: 1, created_at: timestamp, updated_at: timestamp, updated_by: 1,
      }
      feedback.main_requirement_id = requirement.id
      feedback.status = 'REQUIREMENT_LINKED'
      feedback.revision += 1
      return json(requirement)
    }
    const accepted = feedback.status === 'ACCEPTED' || feedback.status === 'REQUIREMENT_LINKED'
    const responses: Record<string, unknown> = {
      '/auth/me': { id: 1, username: 'mock-guide-viewer', display_name: '指定接收人', status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'SELF', role_ids: [], permission_codes: permissionCodes },
      '/notifications/unread-count': { unread_count: 0 },
      '/me/mail-preferences': { revision: 1, mode: 'TASKS', email: null, verified: false, pending_email: null, smtp_enabled: false, notice_acknowledged: true },
      '/systems': { systems: systems.map(system => ({ ...system, enabled: true })), modules: [] },
      '/feedbacks': { items: [feedback], total: 1, page: 1, page_size: 20 },
      '/feedbacks/1': feedback,
      '/feedbacks/1/attachments': [],
      '/feedbacks/1/comments': [],
      '/feedbacks/1/collaboration': { revision: feedback.revision, recipients: [{ id: 1, display_name: '指定接收人' }], handler_id: accepted ? 1 : null, accepted_by: accepted ? 1 : null, accepted_at: accepted ? timestamp : null },
      '/feedbacks/2': other,
      '/feedbacks/2/attachments': [],
      '/feedbacks/2/comments': [],
      '/feedbacks/2/collaboration': { revision: other.revision, recipients: [{ id: 1, display_name: '指定接收人' }], handler_id: 1, accepted_by: 1, accepted_at: timestamp },
      '/requirements/7': requirement,
      '/requirements/7/feedbacks': [{ feedback_id: feedback.id, feedback_no: feedback.feedback_no, title: feedback.title, status: feedback.status, is_primary: true }],
      '/requirements/7/workflow': { revision: 1, content_revision: 1, confirmed_revision: null, needs_confirmation: true, legacy_completed: false, design_status: 'NOT_REQUIRED', paused_from: null, records: [] },
      '/requirements/7/participants': { revision: 1, participants: [{ user_id: 1, role: 'CONFIRM', display_name: '指定接收人', active: true }] },
    }
    if (method === 'GET' && responses[path] !== undefined) return json(responses[path])
    unexpected.push(`${method} ${path}`)
    return json({ message: 'Unexpected API request' }, 500)
  })
  return { statusWrites, conversions, requests, unexpected, pageErrors }
}

async function expectWithinViewport(page: Page, element: Locator, width: number) {
  await expect(element).toBeVisible()
  await expect.poll(async () => {
    const bounds = await element.boundingBox()
    return bounds !== null && bounds.x >= -1 && bounds.x + bounds.width <= width + 1
  }).toBe(true)
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
}

async function expectCreateFormWidth(page: Page, form: Locator, width: number) {
  const panel = form.locator('.el-dialog')
  await expectWithinViewport(page, panel, width)
  await expect.poll(async () => (await panel.boundingBox())?.width ?? 0).toBeCloseTo(Math.min(1040, width - 32), 0)
}

const systemField = (form: Locator) => form.locator('.el-form-item').filter({ hasText: '业务系统' })

async function chooseSystem(page: Page, form: Locator, name: string) {
  await systemField(form).locator('.el-select').click()
  await page.getByRole('option', { name, exact: true }).click()
}

for (const width of [1440, 375]) {
  test(`accepting feedback shows the next step directly below the header and opens a prefilled new requirement at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 1000 })
    const audit = await fixture(page, 'NEW')
    await page.goto('/#/feedbacks/1')
    const header = page.locator('header.page-header').filter({ has: page.getByRole('heading', { name: title }) })
    const belowHeader = header.locator('xpath=following-sibling::*[1]')
    await expect(page.getByText('下一步处理', { exact: true })).toHaveCount(0)
    await header.getByRole('button', { name: '受理', exact: true }).click()
    await page.getByRole('dialog', { name: '受理', exact: true }).getByRole('button', { name: '确定', exact: true }).click()
    await expect(header.getByText('已受理', { exact: true })).toBeVisible()
    await expect(belowHeader).toContainText('下一步处理')
    await expect(header.getByRole('button', { name: /^(转需求|标记重复|无法复现|关闭)$/ })).toHaveCount(0)
    await expectWithinViewport(page, belowHeader, width)
    await expectWithinViewport(page, belowHeader.getByRole('button', { name: '新建需求', exact: true }), width)
    await expectWithinViewport(page, belowHeader.getByRole('button', { name: '关联已有需求', exact: true }), width)
    await expectWithinViewport(page, belowHeader.getByRole('button', { name: '更多处理', exact: true }), width)
    expect(audit.statusWrites).toEqual([{ status: 'ACCEPTED', revision: 4, reason: null, duplicate_of_id: null }])
    await page.screenshot({ path: info.outputPath('accepted-guide.png'), animations: 'disabled' })

    await belowHeader.getByRole('button', { name: '新建需求', exact: true }).click()
    const convert = page.getByRole('dialog', { name: '新建需求', exact: true })
    await expectCreateFormWidth(page, convert, width)
    await expect(convert.getByRole('radio')).toHaveCount(0)
    await expect(convert.getByRole('textbox', { name: /^\*?标题$/ })).toHaveValue(title)
    await expect(convert.getByRole('textbox', { name: '需求描述', exact: true })).toContainText('第二行保留原始语义')
    await expect(convert.getByRole('textbox', { name: '需求描述', exact: true })).toContainText('提交人提供的具体内容')
    const businessSystem = systemField(convert)
    await expect(businessSystem).toContainText('系统甲')
    await expect(businessSystem.getByRole('combobox')).toHaveCount(0)
    await expect(convert.locator('.el-form-item').filter({ hasText: '需求确认人' })).toContainText('指定接收人')
    await expect(convert.getByText('后续人员安排', { exact: false })).toBeVisible()
    await page.screenshot({ path: info.outputPath('prefilled-new-requirement.png'), animations: 'disabled' })
    await convert.getByRole('textbox', { name: '验收标准', exact: true }).fill('保留反馈来源和正文')
    await convert.getByRole('button', { name: '创建', exact: true }).click()
    await expect(page).toHaveURL(/#\/requirements\/7(?:\?|$)/)
    expect(audit.conversions).toHaveLength(1)
    expect(audit.conversions[0]).toEqual({
      type: 'CREATE_NEW', revision: 5, requirement_title: title, requirement_type: 'FEATURE', priority: 'P2',
      description: '<p>提交人提供的具体内容<br>第二行保留原始语义</p>', description_format: 'HTML',
      acceptance_criteria: '保留反馈来源和正文', participants: [{ role: 'CONFIRM', user_id: 1 }], requirement_id: null,
    })

    await page.goto('/#/feedbacks/1')
    await expect(belowHeader.getByRole('link', { name: `REQ-NEXT · ${title}`, exact: true })).toBeVisible()
    await expect(page.getByRole('link', { name: `REQ-NEXT · ${title}`, exact: true })).toHaveCount(1)
    await expect(belowHeader.getByRole('button', { name: /^(新建需求|关联已有需求|更多处理)$/ })).toHaveCount(0)
    await page.screenshot({ path: info.outputPath('linked-requirement.png'), animations: 'disabled' })
    expect(audit.requests).not.toContain('GET /systems/options')
    expect(audit.unexpected).toEqual([])
    expect(audit.pageErrors).toEqual([])
  })

  test(`conversion keeps the draft across fullscreen and Esc from the feedback drawer at ${width}px`, async ({ page }, info) => {
    const height = 640
    await page.setViewportSize({ width, height })
    const audit = await fixture(page, 'ACCEPTED')
    await page.goto('/#/feedbacks?status=ACCEPTED')
    await page.getByText(title, { exact: true }).click()
    const drawer = page.getByRole('dialog', { name: '反馈详情', exact: true })
    const openForm = drawer.getByRole('button', { name: '新建需求', exact: true })
    await openForm.click()
    const form = page.getByRole('dialog', { name: '新建需求', exact: true })
    const titleInput = form.getByRole('textbox', { name: /^\*?标题$/ })
    const editor = form.getByRole('textbox', { name: '需求描述', exact: true })
    const panel = form.locator('.el-dialog')
    const fields = form.locator('.create-form-fields')
    const footer = form.locator('.editor-actions')
    const cancel = footer.getByRole('button', { name: '取消', exact: true })
    await expectCreateFormWidth(page, form, width)

    await titleInput.fill(draftTitle)
    await editor.fill(draftDescription)
    await form.getByRole('button', { name: '全屏编辑', exact: true }).click()
    await expectWithinViewport(page, panel, width)
    await expect.poll(async () => (await panel.boundingBox())?.width ?? 0).toBeCloseTo(width, 0)
    await expect.poll(async () => (await panel.boundingBox())?.height ?? 0).toBeCloseTo(height, 0)
    await expect(titleInput).toHaveValue(draftTitle)
    await expect(editor).toHaveText(draftDescription)
    await page.screenshot({ path: info.outputPath('conversion-fullscreen.png'), animations: 'disabled' })
    await form.getByRole('button', { name: '收起编辑', exact: true }).click()
    await expectCreateFormWidth(page, form, width)

    await cancel.click({ trial: true })
    const footerTop = (await footer.boundingBox())!.y
    await fields.evaluate(element => { element.scrollTop = element.scrollHeight })
    await expect.poll(() => fields.evaluate(element => element.scrollTop)).toBeGreaterThan(0)
    const fieldBounds = (await fields.boundingBox())!
    const footerBounds = (await footer.boundingBox())!
    expect(fieldBounds.y + fieldBounds.height).toBeLessThanOrEqual(footerBounds.y + 1)
    expect(footerBounds.y).toBeCloseTo(footerTop, 0)
    expect(footerBounds.y + footerBounds.height).toBeLessThanOrEqual(height)
    await footer.getByRole('button', { name: '创建', exact: true }).click({ trial: true })

    const prompt = page.getByRole('dialog', { name: '放弃未保存的修改？', exact: true })
    await page.keyboard.press('Escape')
    await expect(prompt).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(prompt).toBeVisible()
    await expect(form).toBeVisible()
    await expect(drawer).toBeVisible()
    await page.screenshot({ path: info.outputPath('conversion-keep-draft.png'), animations: 'disabled' })
    await prompt.getByRole('button', { name: '继续编辑', exact: true }).click()
    await expect(prompt).toBeHidden()
    await expect(titleInput).toHaveValue(draftTitle)
    await expect(editor).toHaveText(draftDescription)

    await form.getByRole('button', { name: '关闭此对话框', exact: true }).click()
    await expect(prompt).toBeVisible()
    await prompt.getByRole('button', { name: '继续编辑', exact: true }).click()
    await expect(prompt).toBeHidden()
    await cancel.click()
    await expect(prompt).toBeVisible()
    await prompt.getByRole('button', { name: '放弃修改', exact: true }).click()
    await expect(form).toBeHidden()
    await expect(drawer).toBeVisible()
    await openForm.click()
    await expect(titleInput).toHaveValue(title)
    await expect(editor).toContainText('第二行保留原始语义')
    expect(audit.conversions).toEqual([])
    expect(audit.statusWrites).toEqual([])
    expect(audit.unexpected).toEqual([])
    expect(audit.pageErrors).toEqual([])
  })

  test(`accepted feedback shows secondary status actions and can reopen from the drawer at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 1000 })
    const audit = await fixture(page, 'ACCEPTED')
    await page.goto('/#/feedbacks?status=ACCEPTED')
    await page.getByText(title, { exact: true }).click()
    const drawer = page.getByRole('dialog', { name: '反馈详情', exact: true })
    const header = drawer.locator('header.page-header')
    const belowHeader = header.locator('xpath=following-sibling::*[1]')
    await expect(belowHeader).toContainText('下一步处理')
    await expectWithinViewport(page, belowHeader, width)
    const more = belowHeader.getByRole('button', { name: '更多处理', exact: true })
    await more.click()
    const actions = page.getByRole('menuitem')
    await expect(actions).toHaveText(['标记为重复反馈', '无法复现', '关闭反馈'])
    await expectWithinViewport(page, actions.last(), width)
    await page.screenshot({ path: info.outputPath('drawer-more-actions.png'), animations: 'disabled' })
    await actions.last().click()
    const close = page.getByRole('dialog', { name: '关闭', exact: true })
    const confirmClose = close.getByRole('button', { name: '确定', exact: true })
    await confirmClose.click()
    expect(audit.statusWrites).toEqual([])
    await close.getByRole('textbox', { name: /原因/ }).fill('现有反馈无需再跟进')
    await confirmClose.click()
    await expect(header.getByText('已关闭', { exact: true })).toBeVisible()
    await expect(drawer.getByText('下一步处理', { exact: true })).toHaveCount(0)
    await header.getByRole('button', { name: '重开', exact: true }).click()
    const reopen = page.getByRole('dialog', { name: '重开', exact: true })
    await reopen.getByRole('textbox', { name: /原因/ }).fill('提交人补充了新的情况')
    await reopen.getByRole('button', { name: '确定', exact: true }).click()
    await expect(header.getByText('待处理', { exact: true })).toBeVisible()
    await expect(header.getByRole('button', { name: '受理', exact: true })).toBeVisible()
    expect(audit.statusWrites).toEqual([
      { status: 'CLOSED', revision: 4, reason: '现有反馈无需再跟进', duplicate_of_id: null },
      { status: 'NEW', revision: 5, reason: '提交人补充了新的情况', duplicate_of_id: null },
    ])
    expect(audit.conversions).toEqual([])
    expect(audit.unexpected).toEqual([])
    expect(audit.pageErrors).toEqual([])
  })
}

test('a feedback-only converter can select a business system for an unbound feedback', async ({ page }, info) => {
  const audit = await fixture(page, 'ACCEPTED', {
    unbound: true, permissionCodes: ['rd.feedback.view', 'rd.feedback.convert'],
  })
  await page.goto('/#/feedbacks/1')
  await page.getByRole('button', { name: '新建需求', exact: true }).click()
  const form = page.getByRole('dialog', { name: '新建需求', exact: true })
  await expect(systemField(form)).toContainText('选择业务系统')
  await expect(page.getByRole('button', { name: '关联已有需求', exact: true })).toHaveCount(0)
  await chooseSystem(page, form, '系统乙')
  await expect(systemField(form)).toContainText('系统乙')
  await page.screenshot({ path: info.outputPath('conversion-selected-system.png'), animations: 'disabled' })
  await form.getByRole('button', { name: '创建', exact: true }).click()
  await expect(form).toBeHidden()
  await expect(page.getByText('当前无法查看关联需求', { exact: true })).toBeVisible()
  await expect(page.locator('.system-attribution')).toContainText('未指定')
  await expect(page).toHaveURL(/#\/feedbacks\/1$/)
  expect(audit.conversions).toHaveLength(1)
  expect(audit.conversions[0]).toMatchObject({ type: 'CREATE_NEW', revision: 4, system_id: 2, participants: [] })
  expect(audit.requests).toContain('GET /systems/options')
  expect(audit.requests).not.toContain('GET /systems')
  expect(audit.requests).not.toContain('GET /requirements/7')
  expect(audit.requests.filter(request => /^(POST|PATCH|PUT|DELETE) /.test(request))).toEqual(['POST /feedbacks/1/convert'])
  expect(audit.unexpected).toEqual([])
  expect(audit.pageErrors).toEqual([])
})

test('the system can remain unset for a conversion from unbound feedback on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const audit = await fixture(page, 'ACCEPTED', { unbound: true })
  await page.goto('/#/feedbacks/1')
  await page.getByRole('button', { name: '新建需求', exact: true }).click()
  const form = page.getByRole('dialog', { name: '新建需求', exact: true })
  await expect(systemField(form)).toContainText('选择业务系统')
  await form.getByRole('button', { name: '创建', exact: true }).click()
  await expect(page).toHaveURL(/#\/requirements\/7(?:\?|$)/)
  await expect(page.locator('.system-attribution')).toContainText('未指定')
  expect(audit.conversions).toHaveLength(1)
  expect(audit.conversions[0]).not.toHaveProperty('system_id')
  expect(audit.unexpected).toEqual([])
  expect(audit.pageErrors).toEqual([])
})

test('a concurrent feedback system assignment requires acknowledging the inherited system before retry', async ({ page }) => {
  const audit = await fixture(page, 'ACCEPTED', { unbound: true, systemConflict: true })
  await page.goto('/#/feedbacks/1')
  await page.getByRole('button', { name: '新建需求', exact: true }).click()
  const form = page.getByRole('dialog', { name: '新建需求', exact: true })
  const titleInput = form.getByRole('textbox', { name: /^\*?标题$/ })
  const submit = form.getByRole('button', { name: '创建', exact: true })
  await titleInput.fill(draftTitle)
  await chooseSystem(page, form, '系统乙')
  await submit.click()
  const conflict = page.getByRole('dialog', { name: '数据已被其他用户修改', exact: true })
  await expect(conflict).toBeVisible()
  await expect(titleInput).toHaveValue(draftTitle)
  expect(audit.conversions).toHaveLength(1)
  expect(audit.conversions[0]).toMatchObject({ revision: 4, system_id: 2 })

  await conflict.getByRole('button', { name: '重新加载服务器版本', exact: true }).click()
  await expect(conflict).toBeHidden()
  await expect(systemField(form)).toContainText('系统甲')
  await expect(systemField(form).getByRole('combobox')).toHaveCount(0)
  await expect(titleInput).toHaveValue(draftTitle)
  await expect(submit).toBeDisabled()
  expect(audit.conversions).toHaveLength(1)
  await form.getByRole('button', { name: '使用反馈的业务系统', exact: true }).click()
  await submit.click()
  await expect(page).toHaveURL(/#\/requirements\/7(?:\?|$)/)
  await expect(page.locator('.system-attribution')).toContainText('系统甲')
  expect(audit.conversions).toHaveLength(2)
  expect(audit.conversions[1]).toMatchObject({ revision: 5, requirement_title: draftTitle })
  expect(audit.conversions[1]).not.toHaveProperty('system_id')
  expect(audit.unexpected).toEqual([])
  expect(audit.pageErrors).toEqual([])
})

test('browser back to another feedback preserves the conversion draft until explicit discard', async ({ page }) => {
  const audit = await fixture(page, 'ACCEPTED')
  await page.goto('/#/feedbacks/2')
  await expect(page.getByRole('heading', { name: '另一条重复反馈', exact: true })).toBeVisible()
  await page.getByRole('link', { name: `FB-NEXT · ${title}`, exact: true }).click()
  await expect(page).toHaveURL(/#\/feedbacks\/1(?:\?|$)/)
  const originalUrl = page.url()
  await page.getByRole('button', { name: '新建需求', exact: true }).click()
  const form = page.getByRole('dialog', { name: '新建需求', exact: true })
  const titleInput = form.getByRole('textbox', { name: /^\*?标题$/ })
  await titleInput.fill(draftTitle)
  const prompt = page.getByRole('dialog', { name: '放弃未保存的修改？', exact: true })
  await page.goBack()
  await expect(prompt).toBeVisible()
  await expect(form).toBeVisible()
  await prompt.getByRole('button', { name: '继续编辑', exact: true }).click()
  await expect(prompt).toBeHidden()
  await expect(page).toHaveURL(originalUrl)
  await expect(titleInput).toHaveValue(draftTitle)
  await page.goBack()
  await expect(prompt).toBeVisible()
  await prompt.getByRole('button', { name: '放弃修改', exact: true }).click()
  await expect(form).toBeHidden()
  await expect(page).toHaveURL(/#\/feedbacks\/2$/)
  await expect(page.getByRole('heading', { name: '另一条重复反馈', exact: true })).toBeVisible()
  expect(audit.conversions).toEqual([])
  expect(audit.unexpected).toEqual([])
  expect(audit.pageErrors).toEqual([])
})
