import { mockReadPanels } from './collaboration-fixture'
import { expect, test } from '@playwright/test'

for (const width of [375, 1440]) {
  test(`assign required roles before content confirmation at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    await page.addInitScript(() => {
      localStorage.setItem('iterflow.access_token', 'confirm-flow-mock')
      localStorage.setItem('iterflow.refresh_token', 'confirm-flow-mock')
    })
    const item = { id: 1, requirement_no: 'REQ-CONFIRM-001', title: '确认前补齐环节人员', requirement_type: 'FEATURE', source: 'DIRECT', priority: 'P1', status: 'DRAFT', owner_id: null, current_version_id: null, description: '旧需求先补齐确认、开发和验收人员。', acceptance_criteria: '分配人员和确认内容分别显式操作。', system_id: null, module_id: null, created_at: '2026-11-02T00:00:00Z', updated_at: '2026-11-02T00:00:00Z', updated_by: 1, revision: 1 }
    let participants: { role: string; user_id: number; display_name: string; active: boolean }[] = []
    let confirmed = false
    const writes: unknown[] = []
    const unexpected: string[] = []
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    const workflow = () => ({ revision: item.revision, content_revision: 1, confirmed_revision: confirmed ? 1 : null, needs_confirmation: !confirmed, legacy_completed: false, design_status: 'NOT_REQUIRED', paused_from: null, records: confirmed ? [{ id: 1, action: 'CONFIRM', actor_id: 1, created_at: '2026-11-02T00:00:00Z', detail: { actor_name: '测试确认人' } }] : [] })
    await page.route('**/api/v1/**', async route => {
      const path = new URL(route.request().url()).pathname
      const method = route.request().method()
      if (path === '/api/v1/requirements/1/participants' && method === 'PUT') {
        const body = route.request().postDataJSON()
        expect(body).toEqual({
          revision: item.revision,
          participants: (item.revision === 1 ? ['CONFIRM'] : ['CONFIRM', 'DEVELOP', 'ACCEPT']).map(role => ({ role, user_id: 1 })),
        })
        writes.push(body)
        participants = body.participants.map((p: { role: string; user_id: number }) => ({ ...p, display_name: '测试确认人', active: true }))
        item.revision++
        return route.fulfill({ json: { revision: item.revision, participants } })
      }
      if (path === '/api/v1/requirements/1/workflow' && method === 'POST') {
        const body = route.request().postDataJSON()
        expect(body).toEqual({ revision: 3, action: 'CONFIRM', reason: null })
        expect(participants.map(p => p.role)).toEqual(['CONFIRM', 'DEVELOP', 'ACCEPT'])
        writes.push(body)
        confirmed = true; item.status = 'CONFIRMED'; item.revision++
        return route.fulfill({ json: workflow() })
      }
      const responses: Record<string, unknown> = {
        '/api/v1/auth/me': { id: 1, username: 'confirm-tester', display_name: '测试确认人', status: 'ACTIVE', must_change_password: false, data_scope: 'ALL', permission_codes: ['*'], can_view_api_docs: true, role_ids: [], revision: 1 },
        '/api/v1/me/mail-preferences': { revision: 1, mode: 'TASKS', email: null, verified: false, pending_email: null, smtp_enabled: false, notice_acknowledged: false },
        '/api/v1/notifications/unread-count': { unread_count: 0 },
        '/api/v1/systems': { systems: [], modules: [] },
        '/api/v1/requirements': { items: [item], total: 1, page: 1, page_size: 20 },
        '/api/v1/requirements/1': item,
        '/api/v1/requirements/1/participants': { revision: item.revision, participants },
        '/api/v1/requirements/1/workflow': workflow(),
        '/api/v1/requirements/1/feedbacks': [],
        '/api/v1/collaboration/people': { items: [{ id: 1, display_name: '测试确认人' }], total: 1, page: 1, page_size: 20 },
      }
      if (!(path in responses) || method !== 'GET') {
        if (await mockReadPanels(route)) return
        unexpected.push(`${method} ${path}`)
        return route.fulfill({ status: 500, json: { message: 'Unexpected request' } })
      }
      return route.fulfill({ json: responses[path] })
    })
    await page.goto('/#/requirements')
    await page.getByText(item.title, { exact: true }).click()
    await page.getByRole('button', { name: '展开需求进度', exact: true }).click()
    await expect(page.getByText('请先在待确认环节设置有效的需求确认人，再确认当前内容。')).toBeVisible()
    await expect(page.getByRole('button', { name: '确认当前内容', exact: true })).toHaveCount(0)
    await page.screenshot({ path: testInfo.outputPath(`missing-confirmer-${width}.png`), fullPage: true })
    await page.getByRole('button', { name: '设置确认人', exact: true }).click()
    const peopleDialog = page.getByRole('dialog', { name: '选择需求确认人', exact: true })
    const legacyConfirmer = peopleDialog.locator('[data-role="CONFIRM"]').getByRole('combobox')
    await peopleDialog.locator('.el-select__wrapper').click()
    const listId = await legacyConfirmer.getAttribute('aria-controls')
    await page.locator(`[id="${listId}"]`).getByRole('option', { name: '测试确认人', exact: true }).click()
    await legacyConfirmer.press('Escape')
    await expect(page.locator(`[id="${listId}"]`)).toBeHidden()
    await peopleDialog.getByRole('button', { name: '保存人员', exact: true }).click()
    await expect(peopleDialog).toBeHidden()
    const steps = page.getByRole('list', { name: '需求阶段' }).locator('li')
    const confirm = page.getByRole('button', { name: '确认当前内容', exact: true })
    const arrange = page.getByRole('button', { name: '设置开发与验收人员', exact: true })
    await expect(steps.nth(0)).toContainText('当前阶段')
    await expect(page.getByText(/尚未设置有效的开发人员、验收人员/)).toBeVisible()
    await expect(confirm).toHaveCount(0)
    await expect(arrange).toBeVisible()
    expect(writes).toHaveLength(1)
    await arrange.click()
    const assignment = page.getByRole('dialog', { name: '安排设计、开发与验收人员', exact: true })
    await expect(assignment).toBeVisible()
    await expect(assignment).toHaveCSS('opacity', '1')
    await expect(page.locator('.el-dialog:visible')).toHaveCount(1)
    await expect(assignment.getByRole('combobox', { name: '设计人员（可选）', exact: true })).toBeVisible()
    await expect(assignment.getByText(/验收人员可多选/)).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath(`pre-confirm-assignment-${width}.png`), fullPage: true })
    await assignment.getByRole('button', { name: '取消', exact: true }).click()
    await expect(assignment).toBeHidden()
    await expect(confirm).toHaveCount(0)
    expect(writes).toHaveLength(1)
    await arrange.click()
    for (const role of ['DEVELOP', 'ACCEPT']) {
      const field = assignment.locator(`[data-role="${role}"]`)
      const selector = field.getByRole('combobox')
      await field.locator('.el-select__wrapper').click()
      const id = await selector.getAttribute('aria-controls')
      await page.locator(`[id="${id}"]`).getByRole('option', { name: '测试确认人', exact: true }).click()
      await selector.press('Escape')
    }
    await assignment.getByRole('button', { name: '保存人员', exact: true }).click()
    await expect(assignment).toBeHidden()
    await expect(steps.nth(0)).toContainText('当前阶段')
    expect(writes).toHaveLength(2)
    await confirm.click()
    const confirmDialog = page.getByRole('dialog', { name: '确认当前内容', exact: true })
    await expect(confirmDialog.getByText('说明（选填）')).toBeVisible()
    await confirmDialog.getByRole('button', { name: '确认操作', exact: true }).click()
    await expect(confirmDialog).toBeHidden()
    await expect(steps.nth(1)).toContainText('当前阶段')
    await expect(page.locator('.el-dialog:visible')).toHaveCount(0)
    await steps.nth(0).getByRole('button').click()
    await expect(page.locator('.step-detail')).toContainText('当前内容已确认')
    await steps.nth(1).getByRole('button').click()
    await expect(page.getByRole('button', { name: '选择 / 调整人员', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: '开始开发', exact: true })).toBeEnabled()
    expect(writes).toHaveLength(3)
    await page.getByRole('button', { name: '收起需求进度', exact: true }).scrollIntoViewIfNeeded()
    await page.screenshot({ path: testInfo.outputPath(`confirmed-${width}.png`), fullPage: true })
    expect(unexpected).toEqual([])
    expect(errors).toEqual([])
  })
}
