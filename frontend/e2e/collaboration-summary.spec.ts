import { expect, test } from '@playwright/test'

for (const width of [375, 390, 768, 1280, 1440]) {
  test(`version requirement summary retains context at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.addInitScript(() => {
      localStorage.setItem('iterflow.access_token', 'test-access')
      localStorage.setItem('iterflow.refresh_token', 'test-refresh')
    })
    const requirement = { id: 9, requirement_no: 'REQ-9', title: '批量关联的重要需求', description: '需要在版本详情内查看的信息', acceptance_criteria: '关闭摘要后保持版本上下文', status: 'DONE', priority: 'P1', requirement_type: 'FEATURE', source: 'DIRECT', revision: 1 }
    await page.route('**/api/v1/**', route => {
      const path = new URL(route.request().url()).pathname
      const json = (body: unknown) => route.fulfill({ status: 200, json: body })
      if (path === '/api/v1/auth/me') return json({ id: 1, username: 'viewer', display_name: '测试用户', status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'ALL', role_ids: [], permission_codes: ['rd.version.view', 'rd.requirement.view', 'rd.feedback.create'] })
      if (path === '/api/v1/notifications/unread-count') return json({ unread_count: 0 })
      if (path === '/api/v1/versions/7') return json({ id: 7, version_no: 'V-NEXT', name: '下一迭代', status: 'PLANNING', revision: 1, created_at: '2026-10-31T00:00:00Z', updated_at: '2026-10-31T00:00:00Z' })
      if (path === '/api/v1/versions/7/requirements') return json({ version_id: 7, items: [requirement], stats: { total: 1, completed: 1, completion_rate: 1, by_status: { DONE: 1 } } })
      if (path === '/api/v1/requirements/9/workflow') return json({ revision: 1, needs_confirmation: false, legacy_completed: true, design_status: 'NOT_REQUIRED', records: [] })
      if (path === '/api/v1/requirements/9/participants') return json({ revision: 1, participants: [{ user_id: 1, role: 'DEVELOP', display_name: '开发人员', active: true }] })
      if (path === '/api/v1/requirements/9') return json(requirement)
      return route.fulfill({ status: 404, json: { message: `Unexpected request ${path}` } })
    })
    await page.goto('/#/versions/7?return_to=%2Fversions%3Fpage%3D2')
    await expect(page.getByRole('heading', { name: '下一迭代' })).toBeVisible()
    const originalUrl = page.url()
    await page.getByText('查看', { exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '需求摘要' })
    await expect(dialog).toBeVisible()
    await expect(dialog.getByText(requirement.description)).toBeVisible()
    await expect(dialog.getByText(requirement.acceptance_criteria)).toBeVisible()
    expect(page.url()).toBe(originalUrl)
    const panel = dialog.locator('.el-dialog')
    if (width < 768) {
      await expect(panel).toHaveClass(/is-fullscreen/)
      await expect(panel).toHaveCSS('width', `${width}px`)
      await expect(panel).toHaveCSS('height', '900px')
    }
    const bounds = await panel.boundingBox()
    expect(bounds!.x).toBeGreaterThanOrEqual(0)
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width + 1)
    await page.screenshot({ path: testInfo.outputPath('requirement-summary.png'), animations: 'disabled' })
    await dialog.getByRole('button', { name: '关闭', exact: true }).click()
    await expect(dialog).not.toBeVisible()
    expect(page.url()).toBe(originalUrl)
    await expect(page.getByRole('heading', { name: '下一迭代' })).toBeVisible()
    await page.goto('/#/feedbacks/new')
    await expect(page.getByRole('heading', { name: '提交反馈' })).toBeVisible()
    await expect(page.getByText('期望结果', { exact: true })).toHaveCount(0)
    await expect(page.getByText('实际结果', { exact: true })).toHaveCount(0)
    expect(errors).toEqual([])
  })
}
