import { expect, test, type Page } from '@playwright/test'

async function setup(page: Page, options: { feedback?: boolean; detail?: boolean; readonly?: boolean; online?: boolean; delegated?: boolean; conflict?: boolean } = {}) {
  const kind = options.feedback ? 'feedbacks' : 'requirements'
  const writes: any[] = [], unexpected: string[] = [], errors: string[] = []
  let conflict = !!options.conflict
  let removed = false
  const actor = options.delegated ? 9 : 1
  const rows = [1, 2, 3, 4].map(id => ({ id, title: `待处理记录${id}`, requirement_no: `REQ-${id}`, feedback_no: `FB-${id}`, requirement_type: 'FEATURE', feedback_type: 'OTHER', urgency: 'NORMAL', source: 'DIRECT', priority: 'P2', status: options.online || id === 3 ? 'ONLINE' : options.feedback ? 'NEW' : 'DRAFT', description: '合成测试内容', description_format: 'PLAIN', acceptance_criteria: '正常处理', revision: 1, owner_id: null, current_version_id: null, main_requirement_id: options.online ? 9 : null, submitter_id: 1, system_id: null, module_id: null, current_handlers: [], created_at: '2026-11-04T00:00:00Z', updated_at: '2026-11-04T00:00:00Z', updated_by: 1 }))
  page.on('pageerror', e => errors.push(e.message))
  await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'issue4-actions'); localStorage.setItem('iterflow.refresh_token', 'issue4-actions') })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname, method = route.request().method()
    if (method === 'DELETE' && path === `/api/v1/${kind}/1`) {
      const body = route.request().postDataJSON(); writes.push(body)
      if (conflict) { conflict = false; rows[0]!.revision = 2; return route.fulfill({ status: 409, json: { code: 40910, message: '记录已被其他用户修改', data: { current_revision: 2 } } }) }
      removed = true
      return route.fulfill({ json: { id: 1, revision: body.revision + 1, deleted: true } })
    }
    if (method === 'POST' && path === `/api/v1/${kind}/batch-actions`) {
      const body = route.request().postDataJSON(); writes.push(body)
      const results = body.items.map((item: { id: number; revision: number }) => item.id === 2 ? { id: 2, success: false, status_code: 409, code: 40910, message: '记录已被其他用户修改', revision: null } : { id: item.id, success: true, status_code: 200, code: 0, message: '操作成功', revision: item.revision + 1 })
      for (const result of results) if (result.success) { rows[result.id - 1]!.revision++; rows[result.id - 1]!.status = options.feedback ? 'ACCEPTED' : 'CONFIRMED' }
      return route.fulfill({ json: { results } })
    }
    const responses: Record<string, unknown> = {
      '/api/v1/auth/me': { id: actor, username: 'actions', display_name: '测试成员', status: 'ACTIVE', must_change_password: false, data_scope: 'ALL', permission_codes: options.readonly ? ['rd.requirement.view', 'rd.feedback.view'] : ['*'], can_view_api_docs: !!options.delegated, role_ids: [], revision: 1 },
      '/api/v1/me/mail-preferences': { revision: 1, mode: 'TASKS', email: null, pending_email: null, verified: false, smtp_enabled: false, notice_acknowledged: true },
      '/api/v1/notifications/unread-count': { unread_count: 0 },
      '/api/v1/systems': { systems: [], modules: [] },
      '/api/v1/requirements/9': { ...rows[0], id: 9, requirement_no: 'REQ-9', title: '已上线关联需求' },
      [`/api/v1/${kind}`]: { items: rows.filter(r => !removed || r.id !== 1), total: removed ? 3 : 4, page: 1, page_size: 20 },
    }
    for (const row of rows) {
      responses[`/api/v1/${kind}/${row.id}`] = row
      responses[`/api/v1/requirements/${row.id}/workflow`] = { revision: row.revision, content_revision: 1, confirmed_revision: row.status === 'DRAFT' ? null : 1, needs_confirmation: row.status === 'DRAFT', legacy_completed: false, design_status: 'NOT_REQUIRED', paused_from: null, records: [] }
      responses[`/api/v1/requirements/${row.id}/participants`] = { revision: row.revision, participants: ['CONFIRM', 'DEVELOP', 'ACCEPT'].map(role => ({ role, user_id: row.id === 4 ? 4 : 1, display_name: '指定人员', active: true })) }
      responses[`/api/v1/requirements/${row.id}/feedbacks`] = []
      responses[`/api/v1/feedbacks/${row.id}/collaboration`] = { revision: row.revision, recipients: [{ id: row.id === 4 ? 4 : 1, display_name: '指定人员' }], handler_id: null, accepted_by: null, accepted_at: null }
      responses[`/api/v1/feedbacks/${row.id}/comments`] = []
      responses[`/api/v1/feedbacks/${row.id}/attachments`] = []
    }
    if (method !== 'GET' || !(path in responses)) { unexpected.push(`${method} ${path}`); return route.fulfill({ status: 500, json: { message: 'Unexpected request' } }) }
    return route.fulfill({ json: responses[path] })
  })
  await page.goto(`/#/${kind}${options.detail ? '/1' : ''}`)
  return { writes, unexpected, errors }
}

function clean(audit: Awaited<ReturnType<typeof setup>>) { expect(audit.errors).toEqual([]); expect(audit.unexpected).toEqual([]) }

for (const width of [375, 1440]) {
  for (const feedback of [false, true]) {
    test(`batch ${feedback ? 'feedback' : 'requirement'} mixed records and no replay ${width}px`, async ({ page }, info) => {
      await page.setViewportSize({ width, height: 900 })
      const audit = await setup(page, { feedback })
      await page.getByRole('button', { name: '批量操作', exact: true }).click()
      const dialog = page.getByRole('dialog', { name: '批量操作', exact: true })
      for (const id of [1, 2, 3, 4]) await dialog.getByText(`#${id} 待处理记录${id}`, { exact: true }).click()
      await dialog.getByRole('button', { name: '检查所选记录', exact: true }).click()
      await expect(dialog.getByRole('button', { name: '执行可操作的 2 项', exact: true })).toBeEnabled()
      await expect(dialog.getByRole('list', { name: '操作前检查' })).toContainText(feedback ? '当前状态不支持此操作' : '当前阶段不支持此操作')
      await expect(dialog.getByRole('list', { name: '操作前检查' })).toContainText(feedback ? '请由指定接收人受理' : '仅对应环节人员可操作')
      expect(audit.writes).toHaveLength(0)
      await dialog.getByRole('button', { name: '执行可操作的 2 项', exact: true }).click()
      await expect(dialog.getByRole('list', { name: '批量操作结果' })).toContainText('#1 成功')
      await expect(dialog.getByRole('list', { name: '批量操作结果' })).toContainText('#2 未完成')
      await expect(dialog.getByRole('list', { name: '批量操作结果' })).toContainText('记录已被其他用户修改')
      await expect(dialog.getByRole('button', { name: /执行可操作|检查所选/ })).toHaveCount(0)
      await expect(dialog.getByRole('checkbox').first()).toBeDisabled()
      expect(audit.writes).toHaveLength(1)
      expect(audit.writes[0].items).toEqual([{ id: 1, revision: 1 }, { id: 2, revision: 1 }])
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      await page.screenshot({ path: info.outputPath('batch-results.png'), fullPage: true })
      clean(audit)
    })

    test(`delete ${feedback ? 'feedback' : 'requirement'} requires reason and refresh after conflict ${width}px`, async ({ page }, info) => {
      await page.setViewportSize({ width, height: 900 })
      const audit = await setup(page, { feedback, detail: true, conflict: true })
      await page.getByRole('button', { name: '删除', exact: true }).click()
      let dialog = page.getByRole('dialog', { name: '确认删除', exact: true })
      await dialog.getByRole('button', { name: '确认删除', exact: true }).click()
      await expect(dialog.getByRole('alert')).toContainText('请填写删除原因')
      expect(audit.writes).toHaveLength(0)
      await dialog.getByRole('textbox').fill('这是重复创建的记录')
      await dialog.getByRole('button', { name: '确认删除', exact: true }).click()
      await expect(dialog.getByRole('alert')).toContainText('记录已被其他用户修改')
      await expect(dialog.getByRole('textbox')).toHaveValue('这是重复创建的记录')
      expect(audit.writes).toHaveLength(1)
      await dialog.getByRole('button', { name: '刷新详情', exact: true }).click()
      await expect(dialog).toBeHidden()
      expect(audit.writes).toHaveLength(1)
      await page.getByRole('button', { name: '删除', exact: true }).click()
      dialog = page.getByRole('dialog', { name: '确认删除', exact: true })
      await dialog.getByRole('textbox').fill('重新核对后确认删除')
      await page.screenshot({ path: info.outputPath('delete-confirm.png'), fullPage: true, animations: 'disabled' })
      await dialog.getByRole('button', { name: '确认删除', exact: true }).click()
      await expect(page).toHaveURL(new RegExp(`/#/${feedback ? 'feedbacks' : 'requirements'}$`))
      expect(audit.writes).toHaveLength(2)
      expect(audit.writes[1].revision).toBe(2)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      clean(audit)
    })
  }

  test(`delegated batch requires reason before sending ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await setup(page, { feedback: true, delegated: true })
    await page.getByRole('button', { name: '批量操作', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '批量操作', exact: true })
    await dialog.getByText('#1 待处理记录1', { exact: true }).click()
    await dialog.getByRole('button', { name: '检查所选记录', exact: true }).click()
    await dialog.getByRole('button', { name: '执行可操作的 1 项', exact: true }).click()
    await expect(dialog.getByRole('alert')).toContainText('请填写关闭或代操作原因')
    expect(audit.writes).toHaveLength(0)
    await dialog.getByRole('textbox').fill('接收人已授权代操作')
    await dialog.getByRole('button', { name: '执行可操作的 1 项', exact: true }).click()
    await expect(dialog.getByRole('list', { name: '批量操作结果' })).toBeVisible()
    expect(audit.writes).toHaveLength(1)
    expect(audit.writes[0].reason).toBe('接收人已授权代操作')
    clean(audit)
  })
  for (const feedback of [false, true]) {
    test(`read-only and online ${feedback ? 'feedback' : 'requirement'} hide mutations ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      const audit = await setup(page, { feedback, readonly: true })
      await expect(page.getByRole('heading', { name: feedback ? '反馈中心' : '需求管理', exact: true })).toBeVisible()
      await expect(page.getByRole('button', { name: '批量操作', exact: true })).toHaveCount(0)
      await page.goto(`/#/${feedback ? 'feedbacks' : 'requirements'}/1`)
      await expect(page.getByRole('button', { name: '删除', exact: true })).toHaveCount(0)
      clean(audit)
    })
    test(`online ${feedback ? 'feedback' : 'requirement'} hides edit and delete ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      const audit = await setup(page, { feedback, detail: true, online: true })
      await expect(page.getByRole('heading', { name: '待处理记录1', exact: true })).toBeVisible()
      await expect(page.getByRole('button', { name: /^(编辑|删除|受理|转需求|确认当前内容)$/ })).toHaveCount(0)
      clean(audit)
    })
  }
}
