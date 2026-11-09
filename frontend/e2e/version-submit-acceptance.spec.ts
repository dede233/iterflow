import { mockReadPanels } from './collaboration-fixture'
import { expect, test, type Page } from '@playwright/test'

type Options = {
  missingAcceptor?: boolean
  editable?: boolean
  readonly?: boolean
  outsider?: boolean
  administrator?: boolean
  moved?: boolean
  needsConfirmation?: boolean
  designPending?: boolean
  unknownResult?: boolean
  requirementList?: boolean
}

async function fixture(page: Page, options: Options = {}) {
  const stamp = '2026-11-04T00:00:00Z'
  const version = { id: 1, system_id: 1, system_name: '系统甲', version_no: 'V-SUBMIT', name: '集中提交验收版本', status: 'DEVELOPING', revision: 8, owner_id: 1, description: '省去开始开发登记，保留独立验收', planned_release_date: null, released_at: null, created_at: stamp, updated_at: stamp, updated_by: 1 }
  const rows = ['CONFIRMED', 'DEVELOPING', 'DRAFT', 'DONE'].map((status, index) => ({
    id: index + 1, requirement_no: `REQ-SUBMIT-${index + 1}`, title: ['已完成开发待登记', '正常开发中需求', '尚未确认的需求', '已通过验收的需求'][index]!,
    status, requirement_type: 'FEATURE', source: 'DIRECT', priority: 'P2', owner_id: null,
    system_id: 1, system_name: '系统甲', current_version_id: options.moved && index === 0 ? 2 : 1,
    description: '仅使用本地合成数据验证集中提交验收', description_format: 'PLAIN', acceptance_criteria: '验收人员确认后才可发布',
    revision: index + 3, current_handlers: [], created_at: stamp, updated_at: stamp, updated_by: 1,
  }))
  const people = new Map(rows.map(row => [row.id, [
    { role: 'CONFIRM', user_id: 1, display_name: '开发小王', active: true },
    { role: 'DEVELOP', user_id: 1, display_name: '开发小王', active: true },
    ...(options.missingAcceptor && row.id === 1 ? [] : [{ role: 'ACCEPT', user_id: 2, display_name: '验收小李', active: true }]),
  ]]))
  const writes: { method: string; path: string; body: any }[] = [], unexpected: string[] = [], errors: string[] = []
  const gets: string[] = []
  let holdVersionRead = false, versionReadPending = false, releaseVersionRead!: () => void
  const versionReadGate = new Promise<void>(resolve => { releaseVersionRead = resolve })
  const actor = options.outsider ? 9 : 1
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'version-submit-local'); localStorage.setItem('iterflow.refresh_token', 'version-submit-local') })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname, method = route.request().method()
    const json = (data: unknown, status = 200) => route.fulfill({ status, json: data })
    const body = method === 'GET' ? null : route.request().postDataJSON()
    if (method !== 'GET') writes.push({ method, path, body })
    else gets.push(path)
    if (method === 'GET' && path === '/api/v1/versions/1' && holdVersionRead) {
      holdVersionRead = false; versionReadPending = true
      await versionReadGate
    }
    if (method === 'PUT' && path === '/api/v1/requirements/1/participants') {
      expect(body.revision).toBe(rows[0]!.revision)
      people.set(1, body.participants.map((person: { role: string; user_id: number }) => ({ ...person, display_name: person.user_id === 2 ? '验收小李' : '开发小王', active: true })))
      rows[0]!.revision++
      return json({ revision: rows[0]!.revision, participants: people.get(1) })
    }
    if (method === 'POST' && path === '/api/v1/versions/1/requirements/submit-acceptance') {
      if (options.unknownResult) return route.abort('failed')
      const results = body.items.map((entry: { id: number; revision: number }) => {
        const row = rows.find(item => item.id === entry.id)!
        if (body.version_revision !== version.revision) return { id: row.id, success: false, status_code: 409, code: 40910, message: '版本清单已变化，请重新检查', revision: null }
        expect(entry.revision).toBe(row.revision)
        expect(['CONFIRMED', 'DEVELOPING']).toContain(row.status)
        if (row.status === 'CONFIRMED') expect(body.reason?.trim().length).toBeGreaterThanOrEqual(2)
        expect(people.get(row.id)!.some(person => person.role === 'ACCEPT')).toBe(true)
        row.status = 'TESTING'; row.revision++
        return { id: row.id, success: true, status_code: 200, code: 0, message: '已提交验收', revision: row.revision }
      })
      return json({ results })
    }
    const permissions = options.readonly ? ['rd.version.view', 'rd.requirement.view']
      : options.editable === false ? ['rd.version.view', 'rd.requirement.view', 'rd.requirement.status'] : ['*']
    const responses: Record<string, unknown> = {
      '/api/v1/systems/options': [{ id: 1, name: '系统甲' }],
      '/api/v1/auth/me': { id: actor, username: 'version-submit-local', display_name: '合成测试人员', status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'ALL', permission_codes: permissions, can_view_api_docs: !!options.administrator, role_ids: [] },
      '/api/v1/me/mail-preferences': { revision: 1, mode: 'TASKS', email: null, pending_email: null, verified: false, smtp_enabled: false, notice_acknowledged: true },
      '/api/v1/notifications/unread-count': { unread_count: 0 }, '/api/v1/systems': { systems: [], modules: [] },
      '/api/v1/versions/1': version,
      '/api/v1/versions/1/requirements': { version_id: 1, items: rows, stats: { total: 4, completed: 1, completion_rate: .25, by_status: Object.fromEntries(rows.map(row => [row.status, rows.filter(other => other.status === row.status).length])) } },
      '/api/v1/versions/2': { ...version, id: 2, system_id: 1, system_name: '系统甲', version_no: 'V-OTHER', name: '切换后的另一个版本', revision: 12 },
      '/api/v1/versions/2/requirements': { version_id: 2, items: [], stats: { total: 0, completed: 0, completion_rate: 0, by_status: {} } },
      '/api/v1/requirements': { items: rows, total: rows.length, page: 1, page_size: 20 },
      '/api/v1/releases': { items: [], total: 0, page: 1, page_size: 20 },
      '/api/v1/collaboration/people': { items: [{ id: 1, display_name: '开发小王' }, { id: 2, display_name: '验收小李' }], total: 2, page: 1, page_size: 20 },
    }
    for (const row of rows) {
      responses[`/api/v1/requirements/${row.id}`] = row
      responses[`/api/v1/requirements/${row.id}/participants`] = { revision: row.revision, participants: people.get(row.id) }
      responses[`/api/v1/requirements/${row.id}/workflow`] = {
        revision: row.revision, content_revision: 2, confirmed_revision: row.status === 'DRAFT' || options.needsConfirmation ? 1 : 2,
        needs_confirmation: row.status === 'DRAFT' || !!options.needsConfirmation, legacy_completed: false,
        design_status: options.designPending ? 'IN_PROGRESS' : 'NOT_REQUIRED', paused_from: null, records: [],
      }
      responses[`/api/v1/requirements/${row.id}/feedbacks`] = []
    }
    if (method === 'GET' && path in responses) return json(responses[path])
    if (await mockReadPanels(route)) return
    unexpected.push(`${method} ${path}`)
    return json({ message: 'Unexpected local synthetic request' }, 500)
  })
  await page.goto(options.requirementList ? '/#/requirements' : '/#/versions/1')
  return { writes, unexpected, errors, gets, rows, people, version, holdNextVersionRead: () => { holdVersionRead = true }, versionReadPending: () => versionReadPending, releaseVersionRead }
}

async function review(page: Page, ids: number[]) {
  await page.getByRole('button', { name: '批量处理需求', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '批量处理需求', exact: true })
  await dialog.getByRole('radio', { name: /^提交验收/ }).check()
  for (const id of ids) await dialog.getByText(`REQ-SUBMIT-${id}`, { exact: true }).click()
  await dialog.getByRole('button', { name: `下一步：检查 ${ids.length} 条需求`, exact: true }).click()
  await expect(dialog.getByRole('list', { name: '操作前检查', exact: true })).toBeVisible()
  return dialog
}

const clean = (audit: Awaited<ReturnType<typeof fixture>>) => { expect(audit.unexpected).toEqual([]); expect(audit.errors).toEqual([]) }
const submits = (audit: Awaited<ReturnType<typeof fixture>>) => audit.writes.filter(write => write.path.endsWith('/submit-acceptance'))

for (const width of [375, 1440]) {
  test(`version submits confirmed and developing requirements with an explicit shortcut explanation ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await fixture(page)
    const dialog = await review(page, [1, 2, 3, 4])
    await expect(dialog).toContainText('可执行 2 条')
    await expect(dialog).toContainText('跳过 2 条')
    await expect(dialog).toContainText('仍由验收人确认')
    await expect(dialog.getByRole('list', { name: '操作前检查' })).toContainText('尚未确认的需求')
    await expect(dialog.getByRole('list', { name: '操作前检查' })).toContainText('已通过验收的需求')
    const submit = dialog.getByRole('button', { name: '确认提交验收（2 条）', exact: true })
    await submit.click()
    await expect(dialog.getByRole('alert')).toContainText('直接提交验收说明')
    expect(audit.writes).toEqual([])
    await dialog.getByRole('textbox', { name: '直接提交验收说明', exact: true }).fill('实际开发已完成，本次集中补充提交验收')
    await expect(dialog.getByRole('alert')).toHaveCount(0)
    await expect(dialog.getByRole('list', { name: '批量处理步骤' })).toBeInViewport({ ratio: 1 })
    await expect(submit).toBeInViewport({ ratio: 1 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: info.outputPath('version-submit-review.png'), fullPage: false, animations: 'disabled' })
    await submit.click()
    await expect(dialog.getByRole('list', { name: '批量操作结果' })).toBeVisible()
    await expect(dialog).toContainText('成功 2 条')
    await expect(dialog).toContainText('跳过 2 条')
    expect(submits(audit)).toHaveLength(1)
    expect(submits(audit)[0]!.body).toEqual({ version_revision: 8, items: [{ id: 1, revision: 3 }, { id: 2, revision: 4 }], reason: '实际开发已完成，本次集中补充提交验收' })
    expect(audit.rows.map(row => row.status)).toEqual(['TESTING', 'TESTING', 'DRAFT', 'DONE'])
    expect(audit.writes.some(write => /\/publish|\/status|\/workflow|\/batch-actions/.test(write.path))).toBe(false)
    await expect(dialog.getByRole('button', { name: /确认.*（|返回调整|下一步/ })).toHaveCount(0)
    await page.screenshot({ path: info.outputPath('version-submit-results.png'), fullPage: false, animations: 'disabled' })
    clean(audit)
  })

  test(`assign missing acceptance personnel and recheck latest revision without automatically submitting ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await fixture(page, { missingAcceptor: true })
    const dialog = await review(page, [1])
    await expect(dialog).toContainText('可执行 0 条')
    await expect(dialog).toContainText('验收人员')
    await dialog.getByRole('button', { name: '设置人员', exact: true }).click()
    const peopleDialog = page.getByRole('dialog', { name: '设置开发与验收人员', exact: true })
    // Cancel first to prove that opening the editor alone does not assign or advance.
    await peopleDialog.getByRole('button', { name: '取消', exact: true }).click()
    await expect(peopleDialog).toBeHidden()
    await expect(dialog).toBeVisible()
    expect(audit.writes).toEqual([])
    await dialog.getByRole('button', { name: '设置人员', exact: true }).click()
    const acceptForm = peopleDialog.locator('.el-form-item').filter({ hasText: '验收人员' })
    await acceptForm.locator('.el-select__wrapper').click()
    const listId = await acceptForm.getByRole('combobox').getAttribute('aria-controls')
    await page.locator(`[id="${listId}"]`).getByRole('option', { name: '验收小李', exact: true }).click()
    await acceptForm.getByRole('combobox').press('Escape')
    await peopleDialog.getByRole('button', { name: '保存人员', exact: true }).click()
    await expect(peopleDialog).toBeHidden()
    await expect(dialog).toContainText('可执行 1 条')
    expect(submits(audit)).toEqual([])
    expect(audit.writes).toHaveLength(1)
    expect(audit.writes[0]!.body).toEqual({ revision: 3, participants: [{ role: 'CONFIRM', user_id: 1 }, { role: 'DEVELOP', user_id: 1 }, { role: 'ACCEPT', user_id: 2 }] })
    expect(audit.rows[0]!.status).toBe('CONFIRMED')
    await dialog.getByRole('textbox', { name: '直接提交验收说明', exact: true }).fill('已完成开发并补齐验收人员')
    await page.screenshot({ path: info.outputPath('version-personnel-rechecked.png'), fullPage: false, animations: 'disabled' })
    await dialog.getByRole('button', { name: '确认提交验收（1 条）', exact: true }).click()
    await expect(dialog.getByRole('list', { name: '批量操作结果' })).toContainText('已提交验收')
    expect(submits(audit)[0]!.body.items).toEqual([{ id: 1, revision: 4 }])
    expect(audit.people.get(1)!.filter(person => person.role === 'CONFIRM')).toEqual([{ role: 'CONFIRM', user_id: 1, display_name: '开发小王', active: true }])
    clean(audit)
  })

  test(`missing personnel remain blocked without personnel edit permission ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await fixture(page, { missingAcceptor: true, editable: false })
    const dialog = await review(page, [1])
    await expect(dialog).toContainText('验收人员')
    await expect(dialog.getByRole('button', { name: '设置人员', exact: true })).toHaveCount(0)
    await expect(dialog.getByRole('button', { name: /确认提交验收/ })).toHaveCount(0)
    await expect(dialog.getByRole('link', { name: '查看详情并处理（新标签页）', exact: true })).toHaveAttribute('href', '#/requirements/1')
    expect(audit.writes).toEqual([]); clean(audit)
  })

  test(`version view permission alone cannot submit requirements ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await fixture(page, { readonly: true })
    await expect(page.getByRole('heading', { name: '集中提交验收版本', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: '批量处理需求', exact: true })).toHaveCount(0)
    expect(audit.writes).toEqual([]); clean(audit)
  })

  test(`ordinary requirement list retains developing-only submission ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await fixture(page, { requirementList: true })
    const dialog = await review(page, [1])
    await expect(dialog).toContainText('仅开发中需求可提交验收')
    await expect(dialog).toContainText('可执行 0 条')
    await expect(dialog.getByRole('button', { name: '设置人员', exact: true })).toHaveCount(0)
    expect(audit.gets).not.toContain('/api/v1/versions/1')
    expect(audit.writes).toEqual([]); clean(audit)
  })
}

for (const blocker of ['moved', 'needsConfirmation', 'designPending', 'outsider'] as const) {
  test(`version submission preserves ${blocker} gate`, async ({ page }) => {
    const audit = await fixture(page, { [blocker]: true })
    const dialog = await review(page, [1])
    await expect(dialog).toContainText('可执行 0 条')
    const hint = { moved: /当前版本|版本归属|移出/, needsConfirmation: /重新确认/, designPending: /设计/, outsider: /指定的开发人员/ }[blocker]
    await expect(dialog.getByRole('list', { name: '操作前检查' })).toContainText(hint)
    await expect(dialog.getByRole('button', { name: /确认提交验收/ })).toHaveCount(0)
    expect(audit.writes).toEqual([]); clean(audit)
  })
}

test('developing-only version submission does not require an artificial shortcut reason', async ({ page }) => {
  const audit = await fixture(page)
  const dialog = await review(page, [2])
  const reason = dialog.getByRole('textbox', { name: '说明（选填）', exact: true })
  await expect(reason).toBeVisible()
  await reason.fill('短')
  await dialog.getByRole('button', { name: '确认提交验收（1 条）', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('至少 2 个字符')
  expect(submits(audit)).toEqual([])
  await reason.fill('')
  await expect(dialog.getByRole('alert')).toHaveCount(0)
  await dialog.getByRole('button', { name: '确认提交验收（1 条）', exact: true }).click()
  await expect(dialog.getByRole('list', { name: '批量操作结果' })).toBeVisible()
  expect(submits(audit)).toHaveLength(1)
  expect(submits(audit)[0]!.body).toMatchObject({ version_revision: 8, items: [{ id: 2, revision: 4 }] })
  expect(submits(audit)[0]!.body.reason ?? null).toBeNull()
  clean(audit)
})

test('delegated version shortcut keeps its separate explanation and actual operator responsibility', async ({ page }) => {
  const audit = await fixture(page, { outsider: true, administrator: true })
  const dialog = await review(page, [1])
  await dialog.getByRole('button', { name: '确认提交验收（1 条）', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('直接提交及代操作说明')
  expect(audit.writes).toEqual([])
  await dialog.getByRole('textbox', { name: '直接提交及代操作说明', exact: true }).fill('已确认实际开发完成，受托集中提交验收')
  await dialog.getByRole('button', { name: '确认提交验收（1 条）', exact: true }).click()
  await expect(dialog.getByRole('list', { name: '批量操作结果' })).toBeVisible()
  expect(submits(audit)[0]!.body.reason).toBe('已确认实际开发完成，受托集中提交验收')
  clean(audit)
})

test('stale version revision produces per-item failure without replay', async ({ page }) => {
  const audit = await fixture(page)
  const dialog = await review(page, [1])
  await dialog.getByRole('textbox', { name: '直接提交验收说明', exact: true }).fill('实际开发已完成，申请验收')
  audit.version.revision++
  await dialog.getByRole('button', { name: '确认提交验收（1 条）', exact: true }).click()
  await expect(dialog.getByRole('list', { name: '批量操作结果' })).toContainText('版本清单已变化，请重新检查')
  await expect(dialog).toContainText('失败 1 条')
  await expect(dialog.getByRole('button', { name: /确认.*（|返回调整|下一步/ })).toHaveCount(0)
  expect(submits(audit)).toHaveLength(1)
  expect(submits(audit)[0]!.body.version_revision).toBe(8)
  expect(audit.rows[0]!.status).toBe('CONFIRMED')
  clean(audit)
})

test('unknown version submission result instructs verification and never replays', async ({ page }) => {
  const audit = await fixture(page, { unknownResult: true })
  const dialog = await review(page, [1])
  await dialog.getByRole('textbox', { name: '直接提交验收说明', exact: true }).fill('实际开发完成，集中提交验收')
  await dialog.getByRole('button', { name: '确认提交验收（1 条）', exact: true }).click()
  await expect(dialog).toContainText('待核对 1 条')
  await expect(dialog.getByRole('list', { name: '批量操作结果' })).toContainText('核对实际状态')
  await expect(dialog.getByRole('button', { name: /确认.*（|返回调整|下一步/ })).toHaveCount(0)
  expect(submits(audit)).toHaveLength(1)
  clean(audit)
})

test('switching versions while checking discards the old context without submitting', async ({ page }) => {
  const audit = await fixture(page)
  await page.getByRole('button', { name: '批量处理需求', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '批量处理需求', exact: true })
  await dialog.getByRole('radio', { name: /^提交验收/ }).check()
  await dialog.getByText('REQ-SUBMIT-1', { exact: true }).click()
  audit.holdNextVersionRead()
  await dialog.getByRole('button', { name: '下一步：检查 1 条需求', exact: true }).click()
  await expect.poll(audit.versionReadPending).toBe(true)
  await page.goto('/#/versions/2')
  await expect(page.getByRole('heading', { name: '切换后的另一个版本', exact: true })).toBeVisible()
  audit.releaseVersionRead()
  await expect(dialog).toHaveCount(0)
  await expect(page.getByRole('button', { name: '批量处理需求', exact: true })).toBeDisabled()
  expect(audit.writes).toEqual([])
  clean(audit)
})
