import { expect, test, type Page } from '@playwright/test'
import { mockCollaboration } from './collaboration-fixture'

async function fixture(page: Page, kind: 'feedback' | 'requirement' | 'version', failure = false) {
  let attempts = 0
  const stamp = '2026-11-06T02:00:00Z'
  const plural = { feedback: 'feedbacks', requirement: 'requirements', version: 'versions' }[kind]
  const base = { id: 7, system_id: 2, system_name: '小程序业务系统', revision: 1, created_at: stamp, updated_at: stamp, created_by: 1, updated_by: 1 }
  const entity = kind === 'feedback'
    ? { ...base, feedback_no: 'FB-ACTIVITY', title: '反馈详情记录', status: 'ACCEPTED', feedback_type: 'OTHER', urgency: 'NORMAL', description: '反馈的重要内容', submitter_id: 1, module_id: null }
    : kind === 'requirement'
    ? { ...base, requirement_no: 'REQ-ACTIVITY', title: '需求详情记录', status: 'DRAFT', requirement_type: 'FEATURE', source: 'DIRECT', priority: 'P2', description: '需求的重要内容', description_format: 'PLAIN', current_version_id: null, module_id: null }
    : { ...base, version_no: 'V-ACTIVITY', name: '版本详情记录', status: 'PLANNING', owner_id: 1, planned_release_date: null, released_at: null, description: '版本的重要内容' }
  const unexpected: string[] = []
  await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'local-activity'); localStorage.setItem('iterflow.refresh_token', 'local-activity') })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    const reply = (json: unknown, status = 200) => route.fulfill({ status, json })
    if (path === '/api/v1/auth/me') return reply({ id: 1, display_name: '测试成员', username: 'local', must_change_password: false, permission_codes: [`rd.${kind}.view`], data_scope: 'SELF', role_ids: [] })
    if (path === '/api/v1/notifications/unread-count') return reply({ unread_count: 0 })
    if (path === `/api/v1/${plural}/7`) return reply(entity)
    if (path === `/api/v1/${plural}/7/activities`) {
      attempts++
      if (failure && attempts === 1) return reply({ message: 'temporary' }, 503)
      return reply(Array.from({ length: 10 }, (_, i) => ({ id: 20-i, action: i === 0 ? 'UPDATE' : 'CONFIRM', operator: { id: i+1, username: `actor-${i+1}`, display_name: `操作人员${i+1}` }, created_at: stamp })))
    }
    if (/\/feedbacks\/7\/(attachments|comments)$/.test(path)) return reply([])
    if (await mockCollaboration(route)) return
    unexpected.push(path); return reply({ message: 'unexpected' }, 500)
  })
  return { plural, unexpected }
}

for (const width of [1440, 375]) {
  for (const kind of ['feedback','requirement','version'] as const) {
    test(`${kind} shows system and ten collapsed activities at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      const f = await fixture(page, kind)
      await page.goto(`/#/${f.plural}/7`)
      await expect(page.locator('.system-attribution')).toHaveText('业务系统小程序业务系统')
      await expect(page.locator('.system-attribution')).toBeVisible()
      const records = page.getByRole('region', { name: '最近操作', exact: true })
      await expect(records).toContainText('操作人员1')
      await expect(records.getByRole('list')).toHaveCount(0)
      await records.getByRole('button', { name: '查看最近 10 条操作' }).click()
      await expect(records.getByRole('listitem')).toHaveCount(10)
      await expect(records.getByRole('listitem').first()).toContainText('操作人员1')
      await page.evaluate(() => window.scrollTo(0, 0))
      await page.screenshot({ path: `test-results/detail-activity-expanded-${kind}-${width}.png`, fullPage: true })
      await records.getByRole('button', { name: '收起操作记录' }).click()
      await expect(records.getByRole('list')).toHaveCount(0)
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
      expect(f.unexpected).toEqual([])
      await page.evaluate(() => window.scrollTo(0, 0))
      await page.screenshot({ path: `test-results/detail-activity-${kind}-${width}.png`, fullPage: true })
    })
  }
}
test('activity errors can retry without hiding requirement content', async ({ page }) => {
  const f = await fixture(page, 'requirement', true)
  await page.goto('/#/requirements/7')
  await expect(page.getByText('需求的重要内容', { exact: true })).toBeVisible()
  const records = page.getByRole('region', { name: '最近操作', exact: true })
  await expect(records).toContainText('暂时无法加载')
  await records.getByRole('button', { name: '重试' }).click()
  await expect(records).toContainText('操作人员1')
  expect(f.unexpected).toEqual([])
})
