import { expect, test, type Page } from '@playwright/test'
import type { DashboardOverview } from '../src/types/dashboard'

const date = '2026-10-01T10:20:30Z'
const longAction = 'FUTURE_ACTION_'.repeat(40)
const overview: DashboardOverview = {
  data_scope: 'ALL',
  feedback: { pending_count: 1, total_count: 1, by_status: { NEW: 1 } },
  requirements: { active_count: 1, total_count: 1, by_status: { CONFIRMED: 1 } },
  versions: { active_count: 1, total_count: 1, by_status: { PLANNING: 1 }, recent_active_versions: [] },
  releases: { total_count: 1, recent_releases: [] },
  activities: [
    { entity_type: 'REQUIREMENT', entity_id: 123, action: 'STATUS_CHANGE', created_at: date },
    { entity_type: 'FEEDBACK', entity_id: 9007199254740991, action: longAction, created_at: date },
    { entity_type: 'VERSION', entity_id: 789, action: 'VERSION_PUBLISH', created_at: date },
    { entity_type: 'RELEASE', entity_id: 104, action: 'RELEASE_CREATE', created_at: date },
  ],
}

async function login(page: Page, feedbackOnly = false) {
  const requests: string[] = []
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    requests.push(path)
    if (path === '/api/v1/auth/login') return route.fulfill({ json: { access_token: 'activity-test', refresh_token: 'activity-refresh', token_type: 'bearer' } })
    if (path === '/api/v1/auth/me') return route.fulfill({ json: {
      id: 1, username: 'activity-reader', display_name: '活动读者', status: 'ACTIVE', revision: 1,
      must_change_password: false, data_scope: 'ALL', role_ids: [1],
      permission_codes: ['dashboard.view', 'rd.feedback.view', ...(feedbackOnly ? [] : ['rd.requirement.view', 'rd.version.view', 'rd.release.view'])],
    } })
    if (path === '/api/v1/notifications/unread-count') return route.fulfill({ json: { unread_count: 0 } })
    if (path === '/api/v1/dashboard/overview') return route.fulfill({ json: feedbackOnly ? {
      ...overview, requirements: null, versions: null, releases: null,
      activities: overview.activities.filter((item) => item.entity_type === 'FEEDBACK'),
    } : overview })
    if (path === '/api/v1/requirements/123') return route.fulfill({ json: {
      id: 123, requirement_no: 'REQ-123', title: '活动关联需求', requirement_type: 'FEATURE',
      status: 'CONFIRMED', priority: 'P1', source: 'DIRECT', description: '需求详情仍由原有接口读取',
      acceptance_criteria: null, owner_id: null, current_version_id: null, revision: 1,
      created_by: 1, updated_by: 1, created_at: date, updated_at: date,
    } })
    if (path === '/api/v1/requirements/123/feedbacks') return route.fulfill({ json: [] })
    throw new Error(`Unexpected ${route.request().method()} ${path}`)
  })
  await page.goto('/#/login')
  await page.getByPlaceholder('用户名').fill('activity-reader')
  await page.getByPlaceholder('密码', { exact: true }).fill('activity-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/#\/$/)
  await expect(page.getByText('最近活动', { exact: true })).toBeVisible()
  return requests
}

async function assertFits(page: Page, width: number) {
  const card = page.locator('.activity-card')
  await card.scrollIntoViewIfNeeded()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
  for (const row of await card.locator('.activity-row').all()) {
    const box = await row.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.x).toBeGreaterThanOrEqual(0)
    expect(box!.x + box!.width).toBeLessThanOrEqual(width + 1)
    await expect(row.locator('time')).toHaveAttribute('datetime', date)
    await expect(row.locator('time')).toContainText('2026')
    expect(await row.evaluate((element) => element.scrollWidth <= element.clientWidth + 1)).toBe(true)
  }
  const action = card.locator('.activity-action').filter({ hasText: longAction })
  await expect(action).toHaveText(`未知操作（${longAction}）`)
  expect(await action.evaluate((element) => {
    const range = document.createRange()
    range.selectNodeContents(element)
    return range.getClientRects().length > 1
  })).toBe(true)
}

for (const width of [375, 390, 768, 1280, 1440]) {
  test(`dashboard activity login, Chinese labels and requirement Hash navigation fit ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await login(page)
    const card = page.locator('.activity-card')
    await expect(card.locator('.activity-row')).toHaveCount(4)
    await expect(card.getByRole('link', { name: /需求 #123/ })).toHaveAttribute('href', '#/requirements/123')
    await expect(card.getByRole('link', { name: /反馈 #9007199254740991/ })).toHaveAttribute('href', '#/feedbacks/9007199254740991')
    await expect(card.getByRole('link', { name: /版本 #789/ })).toHaveAttribute('href', '#/versions/789')
    await expect(card.getByRole('link', { name: /发布记录 #104/ })).toHaveAttribute('href', '#/releases/104')
    await expect(card).toContainText('变更状态')
    await expect(page.getByText('近期活跃版本', { exact: true })).toBeVisible()
    await expect(page.getByText('近期发布', { exact: true })).toBeVisible()
    await assertFits(page, width)
    await card.getByRole('link', { name: /需求 #123/ }).click()
    await expect(page).toHaveURL(/\/#\/requirements\/123$/)
    await expect(page.getByRole('heading', { name: '活动关联需求' })).toBeVisible()
    await expect(page.getByText('需求详情仍由原有接口读取')).toBeVisible()
  })

  test(`feedback-only dashboard activities stay within the permitted domain at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const requests = await login(page, true)
    const card = page.locator('.activity-card')
    await expect(card.locator('.activity-row')).toHaveCount(1)
    await expect(card).toContainText('反馈 #9007199254740991')
    await expect(card.locator('a[href^="#/requirements/"], a[href^="#/versions/"], a[href^="#/releases/"]')).toHaveCount(0)
    await expect(page.getByText('待处理反馈', { exact: true })).toBeVisible()
    await expect(page.getByText('进行中需求', { exact: true })).toHaveCount(0)
    await assertFits(page, width)
    expect(requests.filter((path) => /^\/api\/v1\/(requirements|versions|releases|audits|users)/.test(path))).toEqual([])
  })
}
