import { expect, test } from '@playwright/test'

for (const layout of ['page', 'drawer']) {
for (const width of [320, 375, 768, 1200, 1440, 1800]) {
  test(`assign people from planned stage at ${width}px in ${layout}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    await page.addInitScript(() => {
      localStorage.setItem('iterflow.access_token', 'stage-people-mock')
      localStorage.setItem('iterflow.refresh_token', 'stage-people-mock')
    })
    const people = [
      { id: 1, display_name: '需求确认人' }, { id: 2, display_name: '开发小林' },
      { id: 3, display_name: '验收小李' }, { id: 5, display_name: '验收小陈' }, { id: 4, display_name: '设计小王' },
    ]
    let participants = [{ role: 'CONFIRM', user_id: 1, display_name: '需求确认人', active: true }]
    let revision = 8
    const writes: unknown[] = []
    const unexpected: string[] = []
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/api/v1/**', async route => {
      const path = new URL(route.request().url()).pathname
      if (path === '/api/v1/requirements/1/participants' && route.request().method() === 'PUT') {
        const payload = route.request().postDataJSON()
        writes.push(payload)
        expect(payload.revision).toBe(revision)
        participants = payload.participants.map((p: { role: string; user_id: number }) => ({ ...p, display_name: people.find(person => person.id === p.user_id)!.display_name, active: true }))
        revision++
        return route.fulfill({ json: { revision, participants } })
      }
      const responses: Record<string, unknown> = {
        '/api/v1/auth/me': { id: 1, username: 'stage-tester', display_name: '需求确认人', status: 'ACTIVE', must_change_password: false, data_scope: 'ALL', permission_codes: ['*'], role_ids: [], revision: 1 },
        '/api/v1/me/mail-preferences': { revision: 1, mode: 'TASKS', email: null, verified: false, pending_email: null, smtp_enabled: false, notice_acknowledged: false },
        '/api/v1/notifications/unread-count': { unread_count: 0 },
        '/api/v1/systems': { systems: [], modules: [] },
        '/api/v1/requirements/1': { id: 1, requirement_no: 'REQ-STAGE-001', title: '在进度卡片中安排人员', requirement_type: 'FEATURE', source: 'DIRECT', priority: 'P1', status: 'CONFIRMED', owner_id: null, current_version_id: null, description: '需求确认后，直接在待开发卡片选择设计、开发和验收人员。', acceptance_criteria: '保留需求确认人，人员分配不自动推进阶段。', system_id: null, module_id: null, created_at: '2026-11-02T00:00:00Z', updated_at: '2026-11-02T00:00:00Z', updated_by: 1, revision },
        '/api/v1/requirements/1/participants': { revision, participants },
        '/api/v1/requirements/1/workflow': { revision, content_revision: 1, confirmed_revision: 1, needs_confirmation: false, legacy_completed: false, design_status: 'NOT_REQUIRED', paused_from: null, records: [{ id: 1, action: 'CONFIRM', actor_id: 1, created_at: '2026-11-02T00:00:00Z', detail: { actor_name: '需求确认人' } }] },
        '/api/v1/requirements/1/feedbacks': [],
        '/api/v1/collaboration/people': { items: people, total: people.length, page: 1, page_size: 20 },
      }
      responses['/api/v1/requirements'] = { items: [responses['/api/v1/requirements/1']], total: 1, page: 1, page_size: 20 }
      if (!(path in responses) || route.request().method() !== 'GET') {
        unexpected.push(`${route.request().method()} ${path}`)
        return route.fulfill({ status: 500, json: { message: 'Unexpected request' } })
      }
      return route.fulfill({ json: responses[path] })
    })
    await page.goto(layout === 'drawer' ? '/#/requirements' : '/#/requirements/1')
    if (layout === 'drawer') await page.getByText('在进度卡片中安排人员', { exact: true }).click()
    await page.getByRole('button', { name: '展开需求进度', exact: true }).click()
    const card = page.getByRole('list', { name: '需求阶段' }).locator('li').nth(1)
    await expect(card).toContainText('当前阶段')
    for (const button of await page.locator('.step-people-button').all()) {
      const geometry = await button.evaluate(element => {
        const bounds = element.getBoundingClientRect()
        const cardBounds = element.closest('li')!.getBoundingClientRect()
        const label = element.querySelector('span')!
        const range = document.createRange()
        range.selectNodeContents(label)
        const lines = [...range.getClientRects()]
        return {
          lines: new Set(lines.map(rect => Math.round(rect.top))).size,
          insideCard: bounds.left >= cardBounds.left && bounds.right <= cardBounds.right,
          textFits: lines.every(rect => rect.left >= bounds.left && rect.right <= bounds.right),
        }
      })
      expect(geometry).toEqual({ lines: 1, insideCard: true, textFits: true })
    }
    await card.getByRole('button', { name: '选择 / 调整人员', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '安排设计、开发与验收人员' })
    await expect(dialog).toBeVisible()
    for (const [label, person] of [['设计人员（可选）', '设计小王'], ['开发人员', '开发小林'], ['验收人员', '验收小李'], ['验收人员', '验收小陈']]) {
      await dialog.locator('.el-form-item').filter({ has: page.getByText(label!, { exact: true }) }).locator('.el-select__wrapper').click()
      const listId = await dialog.getByRole('combobox', { name: label, exact: true }).getAttribute('aria-controls')
      await page.locator(`[id="${listId}"]`).getByRole('option', { name: person, exact: true }).click()
      await dialog.getByText('保存人员后，仍需由对应人员执行确认或阶段操作。').click()
      await expect(page.locator(`[id="${listId}"]`)).toBeHidden()
    }
    await page.screenshot({ path: testInfo.outputPath(`stage-people-dialog-${width}.png`), fullPage: true })
    await dialog.getByRole('button', { name: '保存人员', exact: true }).click()
    await expect(dialog).not.toBeVisible()
    await expect(card).toContainText('开发：开发小林')
    await expect(card).toContainText('设计：设计小王')
    await expect(card).toContainText('验收：验收小李、验收小陈')
    await expect(card).toContainText('当前阶段')
    expect(writes).toEqual([{ revision: 8, participants: [
      { role: 'CONFIRM', user_id: 1 }, { role: 'DESIGN', user_id: 4 },
      { role: 'DEVELOP', user_id: 2 }, { role: 'ACCEPT', user_id: 3 }, { role: 'ACCEPT', user_id: 5 },
    ] }])
    await expect(page.getByText('查看 / 调整环节人员', { exact: true })).toHaveCount(0)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    await page.screenshot({ path: testInfo.outputPath(`stage-people-cards-${width}.png`), fullPage: true })
    expect(unexpected).toEqual([])
    expect(errors).toEqual([])
  })
}
}
