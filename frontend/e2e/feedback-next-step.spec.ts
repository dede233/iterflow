import { expect, test, type Locator, type Page } from '@playwright/test'
import type { ConvertFeedbackPayload, Feedback, FeedbackStatusChangePayload, Requirement } from '../src/types/domain'
import { mockReadPanels } from './collaboration-fixture'

const timestamp = '2026-11-18T00:00:00Z'
const title = '已受理后明确反馈处理方向'
const description = '提交人提供的具体内容\n第二行保留原始语义'

async function fixture(page: Page, status: Feedback['status']) {
  const feedback: Feedback = {
    id: 1, feedback_no: 'FB-NEXT', title, feedback_type: 'OTHER', urgency: 'NORMAL',
    status, description, submitter_id: 1, submitter_display_name: '指定接收人', system_id: 1, system_name: '系统甲', module_id: null,
    expected_result: null, actual_result: null, reproduce_steps: null, main_requirement_id: null, duplicate_of_id: null,
    revision: 4, created_at: timestamp, updated_at: timestamp, updated_by: 1,
  }
  let requirement: Requirement | undefined
  const statusWrites: FeedbackStatusChangePayload[] = []
  const conversions: ConvertFeedbackPayload[] = []
  const unexpected: string[] = []
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'feedback-next-step-mock')
    localStorage.setItem('iterflow.refresh_token', 'feedback-next-step-mock')
  })
  await page.route('**/api/v1/**', async route => {
    if (await mockReadPanels(route)) return
    const path = new URL(route.request().url()).pathname.slice('/api/v1'.length)
    const method = route.request().method()
    const json = (body: unknown, responseStatus = 200) => route.fulfill({ status: responseStatus, json: body })
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
      requirement = {
        id: 7, requirement_no: 'REQ-NEXT', title: payload.requirement_title!, requirement_type: 'FEATURE',
        status: 'DRAFT', priority: 'P2', source: 'FEEDBACK', description: payload.description!, description_format: 'HTML',
        system_id: feedback.system_id, system_name: feedback.system_name, module_id: null, owner_id: null, release_frozen: false,
        current_version_id: null, acceptance_criteria: null, revision: 1, created_at: timestamp, updated_at: timestamp, updated_by: 1,
      }
      feedback.main_requirement_id = requirement.id
      feedback.status = 'REQUIREMENT_LINKED'
      feedback.revision += 1
      return json(requirement)
    }
    const accepted = feedback.status === 'ACCEPTED' || feedback.status === 'REQUIREMENT_LINKED'
    const responses: Record<string, unknown> = {
      '/auth/me': { id: 1, username: 'mock-guide-viewer', display_name: '指定接收人', status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'SELF', role_ids: [], permission_codes: ['*'] },
      '/notifications/unread-count': { unread_count: 0 },
      '/me/mail-preferences': { revision: 1, mode: 'TASKS', email: null, verified: false, pending_email: null, smtp_enabled: false, notice_acknowledged: true },
      '/systems': { systems: [{ id: 1, name: '系统甲', enabled: true }], modules: [] },
      '/feedbacks': { items: [feedback], total: 1, page: 1, page_size: 20 },
      '/feedbacks/1': feedback,
      '/feedbacks/1/attachments': [],
      '/feedbacks/1/comments': [],
      '/feedbacks/1/collaboration': { revision: feedback.revision, recipients: [{ id: 1, display_name: '指定接收人' }], handler_id: accepted ? 1 : null, accepted_by: accepted ? 1 : null, accepted_at: accepted ? timestamp : null },
      '/requirements/7': requirement,
      '/requirements/7/feedbacks': [{ feedback_id: feedback.id, feedback_no: feedback.feedback_no, title: feedback.title, status: feedback.status, is_primary: true }],
      '/requirements/7/workflow': { revision: 1, content_revision: 1, confirmed_revision: null, needs_confirmation: true, legacy_completed: false, design_status: 'NOT_REQUIRED', paused_from: null, records: [] },
      '/requirements/7/participants': { revision: 1, participants: [{ user_id: 1, role: 'CONFIRM', display_name: '指定接收人', active: true }] },
    }
    if (method === 'GET' && responses[path] !== undefined) return json(responses[path])
    unexpected.push(`${method} ${path}`)
    return json({ message: 'Unexpected API request' }, 500)
  })
  return { statusWrites, conversions, unexpected, pageErrors }
}

async function expectWithinViewport(page: Page, element: Locator, width: number) {
  await expect(element).toBeVisible()
  await expect.poll(async () => {
    const bounds = await element.boundingBox()
    return bounds !== null && bounds.x >= -1 && bounds.x + bounds.width <= width + 1
  }).toBe(true)
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
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
    await expectWithinViewport(page, convert, width)
    await expect(convert.getByRole('radio')).toHaveCount(0)
    await expect(convert.getByRole('textbox', { name: /需求标题$/ })).toHaveValue(title)
    await expect(convert.getByRole('textbox', { name: '需求描述', exact: true })).toContainText('第二行保留原始语义')
    await expect(convert.getByRole('textbox', { name: '需求描述', exact: true })).toContainText('提交人提供的具体内容')
    await page.screenshot({ path: info.outputPath('prefilled-new-requirement.png'), animations: 'disabled' })
    await convert.getByRole('button', { name: '确定', exact: true }).click()
    await expect(page).toHaveURL(/#\/requirements\/7(?:\?|$)/)
    expect(audit.conversions).toHaveLength(1)
    expect(audit.conversions[0]).toMatchObject({ type: 'CREATE_NEW', revision: 5, requirement_title: title, description_format: 'HTML', participants: [{ role: 'CONFIRM', user_id: 1 }] })
    expect(audit.conversions[0]!.description).toContain('第二行保留原始语义')
    expect(audit.conversions[0]!.description).toContain('提交人提供的具体内容')

    await page.goto('/#/feedbacks/1')
    await expect(belowHeader.getByRole('link', { name: `REQ-NEXT · ${title}`, exact: true })).toBeVisible()
    await expect(page.getByRole('link', { name: `REQ-NEXT · ${title}`, exact: true })).toHaveCount(1)
    await expect(belowHeader.getByRole('button', { name: /^(新建需求|关联已有需求|更多处理)$/ })).toHaveCount(0)
    await page.screenshot({ path: info.outputPath('linked-requirement.png'), animations: 'disabled' })
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
