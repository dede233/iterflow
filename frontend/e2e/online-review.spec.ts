import { expect, test, type Page } from '@playwright/test'
import type { components } from '../src/types/openapi.generated'
import { mockReadPanels } from './collaboration-fixture'

type Review = components['schemas']['OnlineReviewOut']
type Confirmation = components['schemas']['OnlineReviewConfirmation']
type ConfirmRequest = components['schemas']['OnlineReviewConfirm']
type FeedbackRequest = components['schemas']['OnlineReviewFeedbackCreate']

const timestamp = '2026-11-18T00:00:00Z'
const requirementPath = '/requirements/7'
const reviewPath = `${requirementPath}/online-review`
const cardTitle = '线上效果确认'
const confirmLabel = '确认无误'
const confirmDialogTitle = '确认线上效果'
const creatorOnlyReason = '仅需求创建人可确认线上效果。'
const feedbackLabel = '提交线上反馈'
const originalTitle = '发布前的来源反馈'
const followupTitle = '上线后发现的新问题'
const recipient = { id: 2, display_name: '平台值班人员' }
const attachmentName = 'online-feedback.txt'
const allPermissions = ['rd.requirement.view', 'rd.feedback.view', 'rd.feedback.create', 'sys.system.view']

async function fixture(page: Page, { status = 'ONLINE', creator = true, permissions = allPermissions, history = 0 } = {}) {
  const actor = creator ? 1 : 9
  const requirement = {
    id: 7, requirement_no: 'REQ-ONLINE', title: '已交付的流程改进', requirement_type: 'FEATURE', source: 'FEEDBACK',
    priority: 'P2', status, description: '正式验收记录', description_format: 'PLAIN', system_id: 3,
    system_name: '系统甲', release_frozen: status === 'ONLINE', current_version_id: null, owner_id: null,
    acceptance_criteria: '通过独立验收', revision: 4, created_at: timestamp, updated_at: timestamp, updated_by: 1,
  }
  const feedbacks: Review['feedbacks'] = Array.from({ length: history }, (_, i) => ({
    id: 39 - i, feedback_no: `FB-${39 - i}`, title: `历史线上反馈 ${i + 1}`, status: 'NEW', created_at: timestamp,
  }))
  let confirmation: Confirmation | null = null
  const reads: number[] = []
  const confirms: ConfirmRequest[] = []
  const creates: FeedbackRequest[] = []
  const attachments: string[] = []
  const unexpected: string[] = []
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'online-review-fixture')
    localStorage.setItem('iterflow.refresh_token', 'online-review-fixture')
  })
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname.slice('/api/v1'.length)
    const method = route.request().method()
    const json = (body: unknown, status = 200) => route.fulfill({ status, json: body })
    const conflict = () => {
      requirement.revision++
      return json({ code: 40910, message: '需求已被其他用户修改', data: { current_revision: requirement.revision } }, 409)
    }
    if (status === 'ONLINE' && method === 'GET' && path === reviewPath) {
      const currentPage = Number(url.searchParams.get('page') ?? 1)
      reads.push(currentPage)
      const mayReadFeedbacks = permissions.includes('rd.feedback.view')
      const summary: Review = {
        revision: requirement.revision,
        can_confirm: creator && !confirmation,
        confirmation,
        feedbacks: mayReadFeedbacks ? feedbacks.slice((currentPage - 1) * 10, currentPage * 10) : [],
        feedback_total: mayReadFeedbacks ? feedbacks.length : 0,
      }
      return json(summary)
    }
    if (method === 'POST' && path === `${reviewPath}/confirm` && creator && !confirmation) {
      const body: ConfirmRequest = route.request().postDataJSON()
      confirms.push(body)
      expect(body.revision).toBe(requirement.revision)
      if (confirms.length === 1) return conflict()
      confirmation = { confirmed_by: actor, confirmed_by_name: '需求创建人', confirmed_at: timestamp, note: body.note ?? null }
      requirement.revision++
      return json(confirmation)
    }
    if (method === 'POST' && path === `${reviewPath}/feedbacks` && permissions.includes('rd.feedback.create')) {
      const body: FeedbackRequest = route.request().postDataJSON()
      creates.push(body)
      expect(body.revision).toBe(requirement.revision)
      if (creates.length === 1) return conflict()
      const item: Review['feedbacks'][number] = { id: 40, feedback_no: 'FB-40', title: body.title, status: 'NEW', created_at: timestamp }
      feedbacks.unshift(item)
      return json({ ...item, main_requirement_id: null, submitter_id: actor, revision: 1 })
    }
    if (method === 'POST' && path === '/feedbacks/40/attachments' && creates.length === 2) {
      expect(route.request().headers()['content-type']).toContain('multipart/form-data')
      attachments.push(route.request().postData() ?? '')
      return json({ file_id: 101, original_filename: attachmentName })
    }
    const responses: Record<string, unknown> = {
      '/auth/me': { id: actor, username: 'online-review-fixture', display_name: creator ? '需求创建人' : '另一位成员', status: 'ACTIVE', must_change_password: false, role_ids: [], revision: 1, data_scope: 'ALL', permission_codes: permissions },
      '/notifications/unread-count': { unread_count: 0 },
      '/me/mail-preferences': { revision: 1, mode: 'TASKS', smtp_enabled: false, verified: false, notice_acknowledged: true },
      '/systems': { systems: [{ id: 3, name: '系统甲', enabled: true }], modules: [] },
      '/collaboration/people': { items: [recipient], total: 1, page: 1, page_size: 20 },
      [requirementPath]: requirement,
      [`${requirementPath}/workflow`]: { revision: requirement.revision, content_revision: 1, confirmed_revision: 1, needs_confirmation: false, legacy_completed: false, design_status: 'NOT_REQUIRED', paused_from: null, records: [] },
      [`${requirementPath}/participants`]: { revision: requirement.revision, participants: [] },
      [`${requirementPath}/feedbacks`]: [{ feedback_id: 100, feedback_no: 'FB-SOURCE', title: originalTitle, status: 'ONLINE', is_primary: true }],
    }
    if (method === 'GET' && path in responses) return json(responses[path])
    if (await mockReadPanels(route)) return
    unexpected.push(`${method} ${path}`)
    return json({ message: 'Unexpected API request' }, 500)
  })
  await page.goto(`/#${requirementPath}`)
  await expect(page.getByRole('heading', { name: requirement.title, exact: true })).toBeVisible()
  return { confirms, creates, reads, attachments, unexpected, errors }
}

const reviewCard = (page: Page) => page.locator('.section-card').filter({ has: page.getByRole('heading', { name: cardTitle, exact: true }) })

for (const width of [375, 1440]) {
  test(`online review and linked feedback preserve drafts after conflicts at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await fixture(page, { history: 10 })
    const card = reviewCard(page)
    const sourceCard = page.locator('.section-card').filter({ has: page.getByRole('heading', { name: '来源反馈', exact: true }) })
    const confirmAction = card.getByRole('button', { name: confirmLabel, exact: true })
    await expect(card.getByText('待确认', { exact: true })).toBeVisible()
    await expect(confirmAction).toBeVisible()
    await expect(confirmAction).toBeEnabled()
    await expect(sourceCard).toContainText(originalTitle)
    await expect(card).not.toContainText(originalTitle)
    await confirmAction.click()
    expect(audit.confirms).toHaveLength(0)
    const confirm = page.getByRole('dialog', { name: confirmDialogTitle, exact: true })
    const note = confirm.getByRole('textbox', { name: /确认说明/ })
    await note.fill('人工检查后确认达到预期。')
    await confirm.getByRole('button', { name: confirmLabel, exact: true }).click()
    const refreshConfirm = confirm.getByRole('button', { name: '刷新需求信息', exact: true })
    await expect(refreshConfirm).toBeVisible()
    await expect(note).toHaveValue('人工检查后确认达到预期。')
    await refreshConfirm.click()
    await expect(refreshConfirm).toHaveCount(0)
    await expect(note).toHaveValue('人工检查后确认达到预期。')
    expect(audit.confirms).toEqual([{ revision: 4, note: '人工检查后确认达到预期。' }])
    await confirm.getByRole('button', { name: confirmLabel, exact: true }).click()
    await expect(confirm).toBeHidden()
    await expect(card.getByText('人工检查后确认达到预期。', { exact: true })).toBeVisible()
    await expect(card.getByText('已确认', { exact: true })).toBeVisible()
    await expect(card.getByText('需求创建人', { exact: true })).toBeVisible()
    await expect(card.locator(`time[datetime="${timestamp}"]`).first()).toBeVisible()
    await expect(confirmAction).toHaveCount(0)
    expect(audit.confirms.map(({ revision }) => revision)).toEqual([4, 5])

    await card.getByRole('button', { name: feedbackLabel, exact: true }).click()
    const form = page.getByRole('dialog', { name: feedbackLabel, exact: true })
    const title = form.locator('.el-form-item').filter({ hasText: '标题' }).getByRole('textbox')
    const description = form.locator('.el-form-item').filter({ hasText: '详细描述' }).getByRole('textbox')
    const recipients = form.locator('.el-form-item').filter({ hasText: '反馈接收人' })
    const submit = form.getByRole('button', { name: '提交', exact: true })
    await expect(form).toContainText('REQ-ONLINE')
    await title.fill(followupTitle)
    await description.fill('复核已发布功能时发现新的情况。')
    await submit.click()
    await expect(page.getByText('请选择至少一位反馈接收人', { exact: true })).toBeVisible()
    expect(audit.creates).toHaveLength(0)
    await recipients.locator('.el-select__wrapper').click()
    await page.getByRole('option', { name: recipient.display_name, exact: true }).click()
    await description.click()
    await form.locator('input[type="file"]').setInputFiles({ name: attachmentName, mimeType: 'text/plain', buffer: Buffer.from('mock online review attachment') })
    await submit.click()
    const refreshFeedback = form.getByRole('button', { name: '刷新需求信息', exact: true })
    await expect(refreshFeedback).toBeVisible()
    await refreshFeedback.click()
    await expect(refreshFeedback).toHaveCount(0)
    await expect(title).toHaveValue(followupTitle)
    await expect(description).toHaveValue('复核已发布功能时发现新的情况。')
    await expect(recipients).toContainText(recipient.display_name)
    await expect(form.getByText(attachmentName, { exact: true })).toBeVisible()
    expect(audit.creates).toHaveLength(1)
    expect(audit.attachments).toHaveLength(0)
    await expect(submit).toBeInViewport({ ratio: 1 })
    await form.locator('.create-form-fields').evaluate(element => { element.scrollTop = 0 })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    await page.screenshot({ path: info.outputPath('online-feedback-form.png'), animations: 'disabled' })
    await submit.click()
    await expect(form).toBeHidden()
    await expect(page).toHaveURL(/#\/requirements\/7$/)
    await expect(card.getByRole('link', { name: new RegExp(followupTitle) })).toHaveAttribute('href', /feedbacks\/40/)
    await expect(card.getByText('共 11 条', { exact: true })).toBeVisible()
    await expect(card).toContainText('待处理')
    expect(audit.creates).toMatchObject([
      { revision: 6, title: followupTitle, feedback_type: 'SYSTEM_ISSUE', description: '复核已发布功能时发现新的情况。', recipient_ids: [2] },
      { revision: 7, title: followupTitle, feedback_type: 'SYSTEM_ISSUE', description: '复核已发布功能时发现新的情况。', recipient_ids: [2] },
    ])
    expect(audit.attachments).toHaveLength(1)
    expect(audit.attachments[0]).toContain(`filename="${attachmentName}"`)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    await page.screenshot({ path: info.outputPath('online-review-card.png'), fullPage: true, animations: 'disabled' })
    await card.getByRole('button', { name: /下一页|next page/i }).click()
    await expect(card.getByRole('link', { name: /历史线上反馈 10/ })).toBeVisible()
    await expect(card.getByRole('link', { name: new RegExp(followupTitle) })).toHaveCount(0)
    expect(audit.reads.at(-1)).toBe(2)
    expect(audit.unexpected).toEqual([])
    expect(audit.errors).toEqual([])
  })
}

test('online review reads only for published requirements and offers actions by eligibility', async ({ page }) => {
  const draft = await fixture(page, { status: 'DONE' })
  await expect(reviewCard(page)).toHaveCount(0)
  expect(draft.reads).toEqual([])
  expect(draft.unexpected).toEqual([])

  await page.goto('about:blank')
  await page.unroute('**/api/v1/**')
  const viewer = await fixture(page, { creator: false, permissions: ['rd.requirement.view'], history: 2 })
  const card = reviewCard(page)
  const confirmAction = card.getByRole('button', { name: confirmLabel, exact: true })
  await expect(card.getByText('待确认', { exact: true })).toBeVisible()
  await expect(confirmAction).toBeVisible()
  await expect(confirmAction).toBeDisabled()
  await expect(card.getByText(creatorOnlyReason, { exact: true })).toBeVisible()
  await expect(card.getByRole('button', { name: feedbackLabel, exact: true })).toHaveCount(0)
  await expect(card.getByText('线上反馈', { exact: true })).toHaveCount(0)
  await expect(card.getByText(/历史线上反馈|共 2 条/)).toHaveCount(0)
  expect(viewer.reads).toEqual([1])
  expect(viewer.confirms).toEqual([])
  expect(viewer.creates).toEqual([])
  expect(viewer.unexpected).toEqual([])
  expect(viewer.errors).toEqual([])

  await page.goto('about:blank')
  await page.unroute('**/api/v1/**')
  const reporter = await fixture(page, { creator: false, permissions: ['rd.requirement.view', 'rd.feedback.create'] })
  const feedbackAction = card.getByRole('button', { name: feedbackLabel, exact: true })
  await expect(confirmAction).toBeVisible()
  await expect(confirmAction).toBeDisabled()
  await expect(confirmAction).toHaveAccessibleDescription(creatorOnlyReason)
  await expect(card.getByText(creatorOnlyReason, { exact: true })).toBeVisible()
  await expect(feedbackAction).toBeVisible()
  await expect(feedbackAction).toBeEnabled()
  await expect(card.getByText('线上反馈', { exact: true })).toHaveCount(0)
  await feedbackAction.click()
  await expect(page.getByRole('dialog', { name: feedbackLabel, exact: true })).toBeVisible()
  expect(reporter.confirms).toEqual([])
  expect(reporter.creates).toEqual([])
  expect(reporter.unexpected).toEqual([])
  expect(reporter.errors).toEqual([])
})
