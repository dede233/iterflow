import { expect, test, type Locator, type Page } from '@playwright/test'
import type { ConvertFeedbackPayload, Feedback, FeedbackStatusChangePayload, Requirement } from '../src/types/domain'
import { mockReadPanels } from './collaboration-fixture'

const timestamp = '2026-11-18T00:00:00Z'
const title = '已受理后明确反馈处理方向'
const description = '提交人提供的具体内容\n第二行保留原始语义'
const draftTitle = '暂未保存的需求标题'
const draftDescription = '在反馈详情中补充需求内容'
const convertPath = '/feedbacks/1/convert'
const combinedPath = '/feedbacks/1/accept-and-convert'
const combinedWrite = `POST ${combinedPath}`
const systems = [{ id: 1, name: '系统甲' }, { id: 2, name: '系统乙' }]
const existingRequirement: Requirement = {
  id: 7, requirement_no: 'REQ-NEXT', title: '可见范围内已有需求', requirement_type: 'FEATURE',
  status: 'DRAFT', priority: 'P2', source: 'DIRECT', description: '已有需求内容', description_format: 'PLAIN',
  system_id: 1, system_name: '系统甲', module_id: null, owner_id: null, release_frozen: false,
  current_version_id: null, acceptance_criteria: null, revision: 3, created_at: timestamp, updated_at: timestamp, updated_by: 1,
}

async function fixture(page: Page, status: Feedback['status'], {
  unbound = false, permissionCodes = ['*'], systemConflict = false, acceptedElsewhere = false,
  recipientId = 1, admin = false, linkRejected = false, expireOnSearch = false, legacyApi = false,
} = {}) {
  const feedback: Feedback = {
    id: 1, feedback_no: 'FB-NEXT', title, feedback_type: 'OTHER', urgency: 'NORMAL',
    status, description, description_format: 'PLAIN', submitter_id: 1, submitter_display_name: '指定接收人', system_id: unbound ? null : 1, system_name: unbound ? null : '系统甲', module_id: null,
    expected_result: null, actual_result: null, reproduce_steps: null, main_requirement_id: null, duplicate_of_id: null,
    revision: 4, created_at: timestamp, updated_at: timestamp, updated_by: 1,
  }
  const other: Feedback = { ...feedback, id: 2, feedback_no: 'FB-OTHER', title: '另一条重复反馈', status: 'DUPLICATE', duplicate_of_id: feedback.id }
  let requirement = existingRequirement
  let accepted = status === 'ACCEPTED'
  const conversionAuth: (string | undefined)[] = []
  const searchQueries: Record<string, string>[] = []
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
    const url = new URL(route.request().url())
    const path = url.pathname.slice('/api/v1'.length)
    const method = route.request().method()
    requests.push(`${method} ${path}`)
    const json = (body: unknown, responseStatus = 200) => route.fulfill({ status: responseStatus, json: body })
    if (method === 'GET' && path === '/systems/options') return json(systems)
    if (method === 'POST' && path === '/auth/refresh' && expireOnSearch) {
      return json({ access_token: 'feedback-next-step-refreshed', refresh_token: 'feedback-next-step-refresh-next', token_type: 'bearer' })
    }
    if (method === 'GET' && path === '/requirements') {
      searchQueries.push(Object.fromEntries(url.searchParams))
      if (expireOnSearch && route.request().headers().authorization !== 'Bearer feedback-next-step-refreshed') {
        return json({ code: 40101, message: '登录访问令牌已过期' }, 401)
      }
      return json({ items: [existingRequirement], total: 1, page: 1, page_size: 20 })
    }
    if (await mockReadPanels(route)) return
    if (method === 'PATCH' && path === '/feedbacks/1/status') {
      const payload: FeedbackStatusChangePayload = route.request().postDataJSON()
      statusWrites.push(payload)
      feedback.status = payload.status
      if (payload.status === 'NEW') accepted = false
      feedback.revision += 1
      return json(feedback)
    }
    if (method === 'POST' && (path === convertPath || path === combinedPath)) {
      const payload: ConvertFeedbackPayload = route.request().postDataJSON()
      conversions.push(payload)
      conversionAuth.push(route.request().headers().authorization)
      if (legacyApi && path === combinedPath) return json({ detail: 'Not Found' }, 404)
      if ((systemConflict || acceptedElsewhere) && conversions.length === 1) {
        if (systemConflict) Object.assign(feedback, { system_id: 1, system_name: '系统甲' })
        if (acceptedElsewhere) { feedback.status = 'ACCEPTED'; accepted = true }
        feedback.revision += 1
        return json({ code: 40910, message: '服务器版本发生变更', data: { current_revision: feedback.revision, current_updated_at: timestamp, current_updated_by: 2 } }, 409)
      }
      if (linkRejected && payload.type === 'LINK_EXISTING' && conversions.length === 1) {
        return json({ code: 40400, message: '需求不存在或当前不可访问' }, 404)
      }
      if (path === combinedPath) accepted = true
      const system = systems.find(({ id }) => id === (feedback.system_id ?? payload.system_id))
      if (payload.type === 'CREATE_NEW') requirement = {
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
    const responses: Record<string, unknown> = {
      '/auth/me': { id: 1, username: 'mock-guide-viewer', display_name: '指定接收人', status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'SELF', role_ids: [], permission_codes: permissionCodes, can_view_api_docs: admin },
      '/notifications/unread-count': { unread_count: 0 },
      '/collaboration/people': { items: [{ id: 2, display_name: '需求确认成员' }], total: 1, page: 1, page_size: 20 },
      '/me/mail-preferences': { revision: 1, mode: 'TASKS', email: null, verified: false, pending_email: null, smtp_enabled: false, notice_acknowledged: true },
      '/systems': { systems: systems.map(system => ({ ...system, enabled: true })), modules: [] },
      '/feedbacks': { items: [feedback], total: 1, page: 1, page_size: 20 },
      '/feedbacks/1': feedback,
      '/feedbacks/1/attachments': [],
      '/feedbacks/1/comments': [],
      '/feedbacks/1/collaboration': { revision: feedback.revision, recipients: [{ id: recipientId, display_name: recipientId === 1 ? '指定接收人' : '其他接收人' }], handler_id: accepted ? 1 : null, accepted_by: accepted ? 1 : null, accepted_at: accepted ? timestamp : null },
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
  return { feedback, statusWrites, conversions, conversionAuth, requests, searchQueries, unexpected, pageErrors }
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
const combinedTitle = '受理并转需求'

function feedbackWrites(requests: string[]) {
  return requests.filter(request => /^(POST|PATCH|PUT|DELETE) \/feedbacks\//.test(request))
}

async function chooseSystem(page: Page, form: Locator, name: string) {
  await systemField(form).locator('.el-select').click()
  await page.getByRole('option', { name, exact: true }).click()
}

for (const width of [1440, 375]) {
  test(`NEW feedback is accepted and creates a requirement in one request at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await fixture(page, 'NEW')
    await page.goto('/#/feedbacks/1')
    const header = page.locator('header.page-header').filter({ has: page.getByRole('heading', { name: title }) })
    await expect(header.getByText('待处理', { exact: true })).toBeVisible()
    await expect(header.getByRole('button', { name: /^(受理|转需求)$/ })).toHaveCount(0)
    await header.getByRole('button', { name: combinedTitle, exact: true }).click()
    const form = page.getByRole('dialog', { name: combinedTitle, exact: true })
    await expectCreateFormWidth(page, form, width)
    await expect(form.getByRole('radio', { name: '新建需求', exact: true })).toBeChecked()
    await expect(form.getByRole('textbox', { name: /^\*?标题$/ })).toHaveValue(title)
    await expect(form.getByRole('textbox', { name: '需求描述', exact: true })).toContainText('第二行保留原始语义')
    await expect(form.getByRole('textbox', { name: /受理原因/ })).toHaveCount(0)
    await page.screenshot({ path: info.outputPath('accept-and-create.png'), animations: 'disabled' })
    expect(feedbackWrites(audit.requests)).toEqual([])
    await form.getByRole('button', { name: '受理并创建需求', exact: true }).click()
    await expect(page).toHaveURL(/#\/requirements\/7(?:\?|$)/)
    expect(audit.conversions).toHaveLength(1)
    expect(audit.conversions[0]).toMatchObject({
      type: 'CREATE_NEW', accept_on_convert: true, revision: 4,
      requirement_title: title, participants: [{ role: 'CONFIRM', user_id: 1 }],
    })
    expect(audit.conversions[0]).not.toHaveProperty('accept_reason')
    await page.goto('/#/feedbacks/1')
    await expect(page.getByRole('link', { name: `REQ-NEXT · ${title}`, exact: true })).toBeVisible()
    await expect(page.getByText(/^由 指定接收人 于 .+ 确认受理$/)).toBeVisible()
    expect(audit.feedback).toMatchObject({ status: 'REQUIREMENT_LINKED', main_requirement_id: 7, revision: 5 })
    expect(feedbackWrites(audit.requests)).toEqual([combinedWrite])
    expect(audit.unexpected).toEqual([])
    expect(audit.pageErrors).toEqual([])
  })

  test(`NEW feedback from the drawer can link a visible requirement at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await fixture(page, 'NEW')
    await page.goto('/#/feedbacks?status=NEW')
    await page.getByText(title, { exact: true }).click()
    const drawer = page.getByRole('dialog', { name: '反馈详情', exact: true })
    await drawer.getByRole('button', { name: combinedTitle, exact: true }).click()
    const form = page.getByRole('dialog', { name: combinedTitle, exact: true })
    await form.getByText('关联已有需求', { exact: true }).click()
    await expect(form.getByRole('radio', { name: '关联已有需求', exact: true })).toBeChecked()
    expect(audit.searchQueries).toEqual([])
    await form.getByRole('button', { name: '选择需求', exact: true }).click()
    const selector = page.getByRole('dialog', { name: '选择需求', exact: true })
    await selector.getByRole('textbox', { name: '搜索需求', exact: true }).fill('已有需求')
    await expect.poll(() => audit.searchQueries.at(-1)).toMatchObject({ keyword: '已有需求', page: '1' })
    await expect(selector.locator('.selector-option')).toHaveCount(1)
    await selector.locator('.selector-option').filter({ hasText: 'REQ-NEXT' }).click()
    await expect(selector).toBeHidden()
    await expect(form).toContainText('可见范围内已有需求')
    await expect(form.getByRole('textbox', { name: /受理原因/ })).toHaveCount(0)
    await form.getByRole('button', { name: '取消', exact: true }).click()
    const prompt = page.getByRole('dialog', { name: '放弃未保存的修改？', exact: true })
    await expect(prompt).toBeVisible()
    await prompt.getByRole('button', { name: '继续编辑', exact: true }).click()
    await expect(prompt).toBeHidden()
    await expect(form).toContainText('可见范围内已有需求')
    await expectWithinViewport(page, form.locator('.el-dialog'), width)
    await page.screenshot({ path: info.outputPath('accept-and-link.png'), animations: 'disabled' })
    expect(feedbackWrites(audit.requests)).toEqual([])
    await form.getByRole('button', { name: '受理并关联已有需求', exact: true }).click()
    await expect(page.getByRole('heading', { name: existingRequirement.title, exact: true })).toBeVisible()
    expect(audit.conversions).toHaveLength(1)
    expect(audit.conversions[0]).toMatchObject({ type: 'LINK_EXISTING', requirement_id: 7, revision: 4, accept_on_convert: true })
    expect(audit.conversions[0]).not.toHaveProperty('accept_reason')
    await page.goto('/#/feedbacks/1')
    await expect(page.getByRole('link', { name: `REQ-NEXT · ${existingRequirement.title}`, exact: true })).toBeVisible()
    await expect(page.getByText(/^由 指定接收人 于 .+ 确认受理$/)).toBeVisible()
    expect(audit.feedback).toMatchObject({ status: 'REQUIREMENT_LINKED', main_requirement_id: 7, revision: 5 })
    expect(feedbackWrites(audit.requests)).toEqual([combinedWrite])
    expect(audit.unexpected).toEqual([])
    expect(audit.pageErrors).toEqual([])
  })

  test(`historical accepted feedback shows the next step and converts without a new acceptance at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 1000 })
    const audit = await fixture(page, 'ACCEPTED')
    await page.goto('/#/feedbacks/1')
    const header = page.locator('header.page-header').filter({ has: page.getByRole('heading', { name: title }) })
    const belowHeader = header.locator('xpath=following-sibling::*[1]')
    await expect(header.getByText('已受理', { exact: true })).toBeVisible()
    await expect(belowHeader).toContainText('下一步处理')
    await expect(header.getByRole('button', { name: /^(转需求|标记重复|无法复现|关闭)$/ })).toHaveCount(0)
    await expectWithinViewport(page, belowHeader, width)
    await expectWithinViewport(page, belowHeader.getByRole('button', { name: '新建需求', exact: true }), width)
    await expectWithinViewport(page, belowHeader.getByRole('button', { name: '关联已有需求', exact: true }), width)
    await expectWithinViewport(page, belowHeader.getByRole('button', { name: '更多处理', exact: true }), width)
    expect(audit.statusWrites).toEqual([])
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
      type: 'CREATE_NEW', revision: 4, requirement_title: title, requirement_type: 'FEATURE', priority: 'P2',
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

  test(`combined conversion keeps the draft across fullscreen and Esc from the feedback drawer at ${width}px`, async ({ page }, info) => {
    const height = 640
    await page.setViewportSize({ width, height })
    const audit = await fixture(page, 'NEW', { recipientId: 2, admin: true })
    await page.goto('/#/feedbacks?status=NEW')
    await page.getByText(title, { exact: true }).click()
    const drawer = page.getByRole('dialog', { name: '反馈详情', exact: true })
    const openForm = drawer.getByRole('button', { name: '受理并转需求', exact: true })
    await openForm.click()
    const form = page.getByRole('dialog', { name: '受理并转需求', exact: true })
    const titleInput = form.getByRole('textbox', { name: /^\*?标题$/ })
    const editor = form.getByRole('textbox', { name: '需求描述', exact: true })
    const reason = form.getByRole('textbox', { name: /受理原因/ })
    const panel = form.locator('.el-dialog')
    const fields = form.locator('.create-form-fields')
    const footer = form.locator('.editor-actions')
    const cancel = footer.getByRole('button', { name: '取消', exact: true })
    await expectCreateFormWidth(page, form, width)

    await titleInput.fill(draftTitle)
    await editor.fill(draftDescription)
    await reason.fill('这段受理说明仍在编辑')
    await form.getByRole('button', { name: '全屏编辑', exact: true }).click()
    await expectWithinViewport(page, panel, width)
    await expect.poll(async () => (await panel.boundingBox())?.width ?? 0).toBeCloseTo(width, 0)
    await expect.poll(async () => (await panel.boundingBox())?.height ?? 0).toBeCloseTo(height, 0)
    await expect(titleInput).toHaveValue(draftTitle)
    await expect(editor).toHaveText(draftDescription)
    await expect(reason).toHaveValue('这段受理说明仍在编辑')
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
    await footer.getByRole('button', { name: '受理并创建需求', exact: true }).click({ trial: true })

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
    await expect(drawer.getByText('本轮尚无受理记录', { exact: true })).toBeVisible()
    await openForm.click()
    await expect(titleInput).toHaveValue(title)
    await expect(editor).toContainText('第二行保留原始语义')
    await expect(reason).toHaveValue('')
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
    await expect(header.getByRole('button', { name: '受理并转需求', exact: true })).toBeVisible()
    expect(audit.statusWrites).toEqual([
      { status: 'CLOSED', revision: 4, reason: '现有反馈无需再跟进', duplicate_of_id: null },
      { status: 'NEW', revision: 5, reason: '提交人补充了新的情况', duplicate_of_id: null },
    ])
    expect(audit.conversions).toEqual([])
    expect(audit.unexpected).toEqual([])
    expect(audit.pageErrors).toEqual([])
  })
}

for (const initialStatus of ['NEW', 'ACCEPTED'] as const) {
  test(`a feedback-only converter with ${initialStatus} feedback must choose a confirmer`, async ({ page }, info) => {
    const combined = initialStatus === 'NEW'
    const permissionCodes = ['rd.feedback.view', 'rd.feedback.convert']
    if (combined) permissionCodes.push('rd.feedback.edit')
    const audit = await fixture(page, initialStatus, {
      unbound: true, permissionCodes,
    })
    await page.goto('/#/feedbacks/1')
    const entryLabel = combined ? combinedTitle : '新建需求'
    await page.getByRole('button', { name: entryLabel, exact: true }).click()
    const form = page.getByRole('dialog', { name: entryLabel, exact: true })
    await expect(systemField(form)).toContainText('选择业务系统')
    await expect(page.getByRole('button', { name: '关联已有需求', exact: true })).toHaveCount(0)
    await expect(form.getByRole('radio', { name: '关联已有需求', exact: true })).toHaveCount(0)
    await chooseSystem(page, form, '系统乙')
    await expect(systemField(form)).toContainText('系统乙')
    const submit = form.getByRole('button', { name: combined ? '受理并创建需求' : '创建', exact: true })
    const confirmer = form.locator('[data-field="confirm"]')
    await submit.click()
    await expect(confirmer).toContainText('请至少选择一名需求确认人')
    expect(audit.conversions).toHaveLength(0)
    const selector = confirmer.getByRole('combobox')
    await expect(selector).toBeFocused()
    await confirmer.locator('.el-select__wrapper').click()
    await page.getByRole('option', { name: '需求确认成员', exact: true }).click()
    await selector.press('Escape')
    await expect(confirmer).not.toContainText('请至少选择一名需求确认人')
    await page.screenshot({ path: info.outputPath('conversion-selected-system.png'), animations: 'disabled' })
    await submit.click()
    await expect(form).toBeHidden()
    await expect(page.getByText('当前无法查看关联需求', { exact: true })).toBeVisible()
    await expect(page.locator('.system-attribution')).toContainText('未指定')
    await expect(page).toHaveURL(/#\/feedbacks\/1$/)
    expect(audit.conversions).toHaveLength(1)
    expect(audit.conversions[0]).toMatchObject({ type: 'CREATE_NEW', revision: 4, system_id: 2, participants: [{ role: 'CONFIRM', user_id: 2 }] })
    if (combined) expect(audit.conversions[0]?.accept_on_convert).toBe(true)
    else expect(audit.conversions[0]).not.toHaveProperty('accept_on_convert')
    expect(audit.requests).toContain('GET /collaboration/people')
    expect(audit.requests).toContain('GET /systems/options')
    expect(audit.requests).not.toContain('GET /systems')
    expect(audit.requests).not.toContain('GET /requirements/7')
    expect(audit.requests.filter(request => /^(POST|PATCH|PUT|DELETE) /.test(request))).toEqual([combined ? combinedWrite : `POST ${convertPath}`])
    expect(audit.unexpected).toEqual([])
    expect(audit.pageErrors).toEqual([])
  })
}

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

test('an older API leaves the combined draft open when its route is unavailable', async ({ page }) => {
  const audit = await fixture(page, 'NEW', { legacyApi: true })
  await page.goto('/#/feedbacks/1')
  await page.getByRole('button', { name: combinedTitle, exact: true }).click()
  const form = page.getByRole('dialog', { name: combinedTitle, exact: true })
  const titleInput = form.getByRole('textbox', { name: /^\*?标题$/ })
  const editor = form.getByRole('textbox', { name: '需求描述', exact: true })
  await titleInput.fill(draftTitle)
  await editor.fill(draftDescription)
  const submit = form.getByRole('button', { name: '受理并创建需求', exact: true })
  await submit.click()
  await expect(form.getByRole('alert')).toBeVisible()
  await expect(submit).toBeEnabled()
  await expect(titleInput).toHaveValue(draftTitle)
  await expect(editor).toContainText(draftDescription)
  await expect(page).toHaveURL(/#\/feedbacks\/1$/)
  expect(audit.feedback).toMatchObject({ status: 'NEW', main_requirement_id: null, revision: 4 })
  expect(feedbackWrites(audit.requests)).toEqual([combinedWrite])
  expect(audit.conversions).toEqual([expect.objectContaining({ accept_on_convert: true, requirement_title: draftTitle, revision: 4 })])
  expect(audit.unexpected).toEqual([])
  expect(audit.pageErrors).toEqual([])
})

test('a stale combined conversion keeps the feedback NEW and retains the draft for a reviewed retry', async ({ page }) => {
  const audit = await fixture(page, 'NEW', { unbound: true, systemConflict: true, recipientId: 2, admin: true })
  await page.goto('/#/feedbacks/1')
  await page.getByRole('button', { name: combinedTitle, exact: true }).click()
  const form = page.getByRole('dialog', { name: combinedTitle, exact: true })
  const titleInput = form.getByRole('textbox', { name: /^\*?标题$/ })
  const reason = form.getByRole('textbox', { name: /受理原因/ })
  const submit = form.getByRole('button', { name: '受理并创建需求', exact: true })
  await titleInput.fill(draftTitle)
  await reason.fill('保留这段受理说明')
  await chooseSystem(page, form, '系统乙')
  await submit.click()
  const conflict = page.getByRole('dialog', { name: '数据已被其他用户修改', exact: true })
  await expect(conflict).toBeVisible()
  await expect(titleInput).toHaveValue(draftTitle)
  await expect(reason).toHaveValue('保留这段受理说明')
  expect(audit.feedback).toMatchObject({ status: 'NEW', main_requirement_id: null })
  expect(audit.conversions).toHaveLength(1)
  expect(audit.conversions[0]).toMatchObject({ revision: 4, system_id: 2, accept_on_convert: true, accept_reason: '保留这段受理说明' })

  await conflict.getByRole('button', { name: '重新加载服务器版本', exact: true }).click()
  await expect(conflict).toBeHidden()
  await expect(systemField(form)).toContainText('系统甲')
  await expect(systemField(form).getByRole('combobox')).toHaveCount(0)
  await expect(titleInput).toHaveValue(draftTitle)
  await expect(reason).toHaveValue('保留这段受理说明')
  await expect(submit).toBeDisabled()
  expect(audit.conversions).toHaveLength(1)
  await form.getByRole('button', { name: '使用反馈的业务系统', exact: true }).click()
  await submit.click()
  await expect(page).toHaveURL(/#\/requirements\/7(?:\?|$)/)
  await expect(page.locator('.system-attribution')).toContainText('系统甲')
  expect(audit.conversions).toHaveLength(2)
  expect(audit.conversions[1]).toMatchObject({ revision: 5, requirement_title: draftTitle, accept_on_convert: true, accept_reason: '保留这段受理说明' })
  expect(audit.conversions[1]).not.toHaveProperty('system_id')
  expect(feedbackWrites(audit.requests)).toEqual([combinedWrite, combinedWrite])
  expect(audit.unexpected).toEqual([])
  expect(audit.pageErrors).toEqual([])
})

test('unavailable link leaves both the feedback and the combined editor intact', async ({ page }) => {
  const audit = await fixture(page, 'NEW', { linkRejected: true, recipientId: 2, admin: true })
  await page.goto('/#/feedbacks/1')
  await page.getByRole('button', { name: combinedTitle, exact: true }).click()
  const form = page.getByRole('dialog', { name: combinedTitle, exact: true })
  const linkMode = form.getByRole('radio', { name: '关联已有需求', exact: true })
  await form.getByText('关联已有需求', { exact: true }).click()
  await expect(linkMode).toBeChecked()
  await form.getByRole('button', { name: '选择需求', exact: true }).click()
  await page.getByRole('dialog', { name: '选择需求', exact: true }).locator('.selector-option').click()
  const reason = form.getByRole('textbox', { name: /受理原因/ })
  await reason.fill('目标需求需要继续核对')
  await form.getByRole('button', { name: '受理并关联已有需求', exact: true }).click()
  await expect(form.getByRole('alert')).toContainText(/不存在|无法访问|无权查看/)
  await expect(linkMode).toBeChecked()
  await expect(reason).toHaveValue('目标需求需要继续核对')
  expect(audit.feedback).toMatchObject({ status: 'NEW', main_requirement_id: null, revision: 4 })
  expect(feedbackWrites(audit.requests)).toEqual([combinedWrite])
  expect(audit.unexpected).toEqual([])
  expect(audit.pageErrors).toEqual([])
})

test('a feedback accepted elsewhere blocks resubmission from the stale combined editor', async ({ page }) => {
  const audit = await fixture(page, 'NEW', { acceptedElsewhere: true })
  await page.goto('/#/feedbacks/1')
  await page.getByRole('button', { name: combinedTitle, exact: true }).click()
  const form = page.getByRole('dialog', { name: combinedTitle, exact: true })
  const titleInput = form.getByRole('textbox', { name: /^\*?标题$/ })
  await titleInput.fill(draftTitle)
  const submit = form.getByRole('button', { name: '受理并创建需求', exact: true })
  await submit.click()
  const conflict = page.getByRole('dialog', { name: '数据已被其他用户修改', exact: true })
  await conflict.getByRole('button', { name: '重新加载服务器版本', exact: true }).click()
  await expect(conflict).toBeHidden()
  await expect(form).toContainText('反馈状态已变为「已受理」')
  await expect(titleInput).toHaveValue(draftTitle)
  await expect(submit).toBeDisabled()
  expect(audit.feedback).toMatchObject({ status: 'ACCEPTED', main_requirement_id: null, revision: 5 })
  expect(feedbackWrites(audit.requests)).toEqual([combinedWrite])
  expect(audit.unexpected).toEqual([])
  expect(audit.pageErrors).toEqual([])
})

test('eligible administrator needs a reason to accept on behalf of the feedback recipient', async ({ page }) => {
  const audit = await fixture(page, 'NEW', { recipientId: 2, admin: true })
  await page.goto('/#/feedbacks/1')
  await page.getByRole('button', { name: combinedTitle, exact: true }).click()
  const form = page.getByRole('dialog', { name: combinedTitle, exact: true })
  const reason = form.getByRole('textbox', { name: /代受理原因/ })
  const submit = form.getByRole('button', { name: '受理并创建需求', exact: true })
  await submit.click()
  await expect(form).toContainText(/至少 ?2 ?个字符/)
  expect(feedbackWrites(audit.requests)).toEqual([])
  await reason.fill('接收人委托跟进本反馈')
  await submit.click()
  await expect(page).toHaveURL(/#\/requirements\/7(?:\?|$)/)
  expect(audit.conversions).toHaveLength(1)
  expect(audit.conversions[0]).toMatchObject({ accept_on_convert: true, accept_reason: '接收人委托跟进本反馈', revision: 4 })
  expect(feedbackWrites(audit.requests)).toEqual([combinedWrite])
  expect(audit.unexpected).toEqual([])
  expect(audit.pageErrors).toEqual([])
})

test('normal access token refresh keeps the active combined conversion draft', async ({ page }) => {
  const audit = await fixture(page, 'NEW', { expireOnSearch: true, recipientId: 2, admin: true })
  await page.goto('/#/feedbacks/1')
  await page.getByRole('button', { name: combinedTitle, exact: true }).click()
  const form = page.getByRole('dialog', { name: combinedTitle, exact: true })
  const titleInput = form.getByRole('textbox', { name: /^\*?标题$/ })
  await titleInput.fill(draftTitle)
  await form.getByRole('textbox', { name: /受理原因/ }).fill('刷新登录令牌后仍需保留')
  await form.getByText('关联已有需求', { exact: true }).click()
  await form.getByRole('button', { name: '选择需求', exact: true }).click()
  const selector = page.getByRole('dialog', { name: '选择需求', exact: true })
  await expect(selector.locator('.selector-option')).toHaveCount(1)
  expect(audit.requests.filter(request => request === 'POST /auth/refresh')).toHaveLength(1)
  expect(audit.searchQueries).toHaveLength(2)
  await selector.getByRole('button', { name: '取消', exact: true }).click()
  await form.getByText('新建需求', { exact: true }).click()
  await expect(titleInput).toHaveValue(draftTitle)
  await expect(form.getByRole('textbox', { name: /受理原因/ })).toHaveValue('刷新登录令牌后仍需保留')
  expect(feedbackWrites(audit.requests)).toEqual([])
  await form.getByRole('button', { name: '受理并创建需求', exact: true }).click()
  await expect(page).toHaveURL(/#\/requirements\/7(?:\?|$)/)
  expect(audit.conversionAuth).toEqual(['Bearer feedback-next-step-refreshed'])
  expect(audit.conversions).toEqual([expect.objectContaining({ accept_on_convert: true, revision: 4, requirement_title: draftTitle })])
  expect(audit.unexpected).toEqual([])
  expect(audit.pageErrors).toEqual([])
})

for (const [label, permissionCodes, recipientId] of [
  ['edit without conversion', ['rd.feedback.edit'], 1],
  ['conversion without edit', ['rd.feedback.convert'], 1],
  ['conversion and edit without recipient eligibility', ['rd.feedback.convert', 'rd.feedback.edit'], 2],
] as const) {
  test(`NEW combined action requires acceptance and conversion authority (${label})`, async ({ page }) => {
    const audit = await fixture(page, 'NEW', { permissionCodes: ['rd.feedback.view', ...permissionCodes], recipientId })
    await page.goto('/#/feedbacks/1')
    await expect(page.getByText('本轮尚无受理记录', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: /^(受理|受理并转需求)$/ })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '转需求', exact: true })).toHaveCount(permissionCodes.some(code => code === 'rd.feedback.convert') ? 1 : 0)
    expect(feedbackWrites(audit.requests)).toEqual([])
    expect(audit.unexpected).toEqual([])
    expect(audit.pageErrors).toEqual([])
  })
}

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
