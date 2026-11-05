import { expect, test, type Page } from '@playwright/test'

const stamp = '2026-11-04T00:00:00Z'
type Options = { status?: string; linked?: boolean; permissions?: string[]; failSequence?: ('duplicate' | 'revision' | 'unavailable')[] }
async function fixture(page: Page, options: Options = {}) {
  const requirement = { id: 7, system_id: 1, system_name: '系统甲', requirement_no: 'REQ-CREATE-VERSION', title: '从需求创建独立版本', requirement_type: 'FEATURE', source: 'DIRECT', priority: 'P2', status: options.status || 'DONE', owner_id: null, current_version_id: options.linked ? 9 : null, description: '已完成验收的需求说明', description_format: 'PLAIN', acceptance_criteria: '保留需求上下文', revision: 4, created_at: stamp, updated_at: stamp, updated_by: 1 }
  const version = { id: 9, system_id: 1, system_name: '系统甲', version_no: 'V2', name: requirement.title, status: 'PLANNING', owner_id: null, planned_release_date: null, released_at: null, description: null as string | null, revision: 2, created_at: stamp, updated_at: stamp, updated_by: 1 }
  const writes: Record<string, any>[] = [], unexpected: string[] = [], errors: string[] = []
  let latestRequirementRevision = 4
  let requirementReads = 0
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'version-source-local'); localStorage.setItem('iterflow.refresh_token', 'version-source-local') })
  await page.route('**/api/v1/**', async route => {
    const method = route.request().method(), path = new URL(route.request().url()).pathname
    const json = (data: unknown, status = 200) => route.fulfill({ status, json: data })
    if (method === 'POST' && path === '/api/v1/versions') {
      const body = route.request().postDataJSON(); writes.push(body)
      const failure = options.failSequence?.[writes.length - 1]
      if (failure === 'duplicate') return json({ code: 40934, message: `版本号「${body.version_no}」已存在，请更换版本号；如需添加需求，请使用已有版本。`, data: { field: 'version_no', reason: 'duplicate' } }, 409)
      if (failure === 'revision') {
        latestRequirementRevision = 5
        return json({ code: 40910, message: '需求已被其他用户修改', data: { current_revision: 5 } }, 409)
      }
      if (failure === 'unavailable') return json({ code: 40300, message: '当前需求已不可关联，请检查权限' }, 403)
      if (body.requirement_id) {
        expect(body.requirement_id).toBe(7); expect(body.requirement_revision).toBe(latestRequirementRevision)
        requirement.current_version_id = 9; requirement.revision = latestRequirementRevision + 1
        version.status = requirement.status === 'DONE' ? 'READY' : 'PLANNING'
      }
      Object.assign(version, { version_no: body.version_no, name: body.name, description: body.description })
      return json(version)
    }
    if (method === 'GET' && path === '/api/v1/requirements/7') {
      requirementReads++
      requirement.revision = Math.max(requirement.revision, latestRequirementRevision)
      return json(requirement)
    }
    const responses: Record<string, unknown> = {
      '/api/v1/systems/options': [{ id: 1, name: '系统甲' }],
      '/api/v1/auth/me': { id: 1, username: 'source-local', display_name: '本地合成用户', status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'ALL', role_ids: [], permission_codes: options.permissions || ['*'] },
      '/api/v1/me/mail-preferences': { revision: 1, mode: 'TASKS', email: null, pending_email: null, verified: false, smtp_enabled: false, notice_acknowledged: true },
      '/api/v1/notifications/unread-count': { unread_count: 0 }, '/api/v1/systems': { systems: [], modules: [] },
      '/api/v1/requirements': { items: [requirement], total: 1, page: 1, page_size: 20 },
      '/api/v1/requirements/7/feedbacks': [],
      '/api/v1/requirements/7/workflow': { revision: requirement.revision, content_revision: 1, confirmed_revision: 1, needs_confirmation: false, legacy_completed: false, design_status: 'NOT_REQUIRED', paused_from: null, records: [] },
      '/api/v1/requirements/7/participants': { revision: requirement.revision, participants: ['CONFIRM', 'DEVELOP', 'ACCEPT'].map(role => ({ role, user_id: 1, display_name: '本地合成用户', active: true })) },
      '/api/v1/versions': { items: [], total: 0, page: 1, page_size: 20 },
      '/api/v1/versions/9': version,
      '/api/v1/versions/9/requirements': { version_id: 9, items: requirement.current_version_id === 9 ? [requirement] : [], stats: { total: requirement.current_version_id === 9 ? 1 : 0, completed: 1, completion_rate: 1, by_status: { DONE: 1 } } },
      '/api/v1/releases': { items: [], total: 0, page: 1, page_size: 20 },
    }
    if (method === 'GET' && path in responses) return json(responses[path])
    unexpected.push(`${method} ${path}`)
    return json({ message: 'Unexpected synthetic request' }, 500)
  })
  return { requirement, writes, unexpected, errors, reads: () => requirementReads }
}
const clean = (audit: Awaited<ReturnType<typeof fixture>>) => { expect(audit.errors).toEqual([]); expect(audit.unexpected).toEqual([]) }

for (const width of [375, 1440]) {
  test(`requirement creates and links a version after explicit duplicate/CAS correction at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await fixture(page, { failSequence: ['duplicate', 'revision'] })
    await page.goto('/#/requirements?keyword=source&status=DONE')
    await page.getByText(audit.requirement.title, { exact: true }).click()
    const detail = page.getByRole('dialog', { name: '需求详情', exact: true })
    await detail.getByRole('button', { name: '创建版本', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '创建版本并关联需求', exact: true })
    const number = dialog.getByRole('textbox', { name: /版本号/ })
    const name = dialog.getByRole('textbox', { name: /版本名称/ })
    const description = dialog.getByRole('textbox', { name: '说明', exact: true })
    await expect(name).toHaveValue(audit.requirement.title)
    await number.fill('V1'); await name.fill('自定义版本名称'); await description.fill('保留的版本说明')
    await dialog.getByRole('button', { name: '创建并关联', exact: true }).click()
    await expect(dialog.getByText('版本号「V1」已存在，请更换版本号；如需添加需求，请使用已有版本。', { exact: true })).toBeVisible()
    await expect(page.getByText('服务器版本已变化，请查看冲突详情', { exact: true })).toHaveCount(0)
    await expect(name).toHaveValue('自定义版本名称'); await expect(description).toHaveValue('保留的版本说明')
    await number.fill('V2')
    await dialog.getByRole('button', { name: '创建并关联', exact: true }).click()
    await expect(dialog.getByRole('alert').filter({ hasText: '请先刷新需求' })).toBeVisible()
    expect(audit.writes).toHaveLength(2)
    await dialog.getByRole('button', { name: '刷新需求', exact: true }).click()
    await expect.poll(() => audit.reads()).toBe(2)
    await expect(dialog.getByRole('button', { name: '刷新需求', exact: true })).toHaveCount(0)
    await expect(name).toHaveValue('自定义版本名称'); await expect(description).toHaveValue('保留的版本说明')
    expect(audit.writes).toHaveLength(2)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await page.screenshot({ path: info.outputPath('source-version-form.png'), animations: 'disabled' })
    await dialog.getByRole('button', { name: '创建并关联', exact: true }).click()
    await expect(dialog).toBeHidden()
    await expect(detail.getByRole('button', { name: '创建版本', exact: true })).toHaveCount(0)
    await expect(detail.getByRole('link', { name: 'V2 · 自定义版本名称', exact: true })).toBeVisible()
    expect(audit.writes).toHaveLength(3)
    expect(audit.writes[2]).toMatchObject({ system_id: 1, version_no: 'V2', name: '自定义版本名称', description: '保留的版本说明', requirement_id: 7, requirement_revision: 5 })
    await expect(page).toHaveURL(/#\/requirements\?keyword=source&status=DONE$/)
    await detail.getByRole('link', { name: 'V2 · 自定义版本名称', exact: true }).click()
    await expect(page.getByRole('heading', { name: '自定义版本名称', exact: true })).toBeVisible()
    expect(new URLSearchParams(page.url().split('?')[1]).get('return_to')).toBe('/requirements?keyword=source&status=DONE')
    expect(audit.requirement.status).toBe('DONE')
    clean(audit)
  })

  test(`normal version creation retains independent form and duplicate correction at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await fixture(page, { failSequence: ['duplicate'] })
    await page.goto('/#/versions')
    await page.getByRole('button', { name: '新建版本', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '新建版本', exact: true })
    await expect(dialog.getByRole('textbox', { name: /版本名称/ })).toHaveValue('')
    await dialog.getByRole('textbox', { name: /版本名称/ }).fill('普通版本创建')
    await dialog.locator('.el-form-item').filter({ hasText: '业务系统' }).locator('.el-select').click()
    await page.getByRole('option', { name: '系统甲', exact: true }).click()
    await dialog.getByRole('textbox', { name: /版本号/ }).fill('V1')
    await dialog.getByRole('button', { name: '创建', exact: true }).click()
    await expect(dialog.getByText(/版本号「V1」已存在/)).toBeVisible()
    await dialog.getByRole('textbox', { name: /版本号/ }).fill('V3')
    await dialog.getByRole('button', { name: '创建', exact: true }).click()
    await expect(dialog).toBeHidden()
    await expect(page.getByRole('heading', { name: '普通版本创建', exact: true })).toBeVisible()
    expect(audit.writes).toHaveLength(2)
    expect(audit.writes[1]).not.toHaveProperty('requirement_id')
    expect(audit.writes[1]).not.toHaveProperty('requirement_revision')
    clean(audit)
  })

  test(`source creation preserves inputs after non-conflict refusal at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await fixture(page, { failSequence: ['unavailable'] })
    await page.goto('/#/requirements/7')
    await page.getByRole('button', { name: '创建版本', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '创建版本并关联需求', exact: true })
    await dialog.getByRole('textbox', { name: /版本号/ }).fill('V1')
    await dialog.getByRole('button', { name: '创建并关联', exact: true }).click()
    await expect(dialog.getByRole('alert')).toHaveText('当前需求已不可关联，请检查权限')
    await expect(dialog.getByRole('textbox', { name: /版本号/ })).toHaveValue('V1')
    expect(audit.writes).toHaveLength(1)
    clean(audit)
  })
}

for (const [label, options] of [
  ['already linked', { linked: true }], ['online', { status: 'ONLINE' }], ['canceled', { status: 'CANCELED' }],
  ['without version edit', { permissions: ['rd.requirement.view', 'rd.version.create', 'rd.version.view'] }],
  ['without version view', { permissions: ['rd.requirement.view', 'rd.version.create', 'rd.version.edit'] }],
  ['without version create', { permissions: ['rd.requirement.view', 'rd.version.view', 'rd.version.edit'] }],
] as const) {
  test(`source entry is unavailable when ${label}`, async ({ page }) => {
    const audit = await fixture(page, options as Options)
    await page.goto('/#/requirements/7')
    await expect(page.getByRole('heading', { name: audit.requirement.title, exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: '创建版本', exact: true })).toHaveCount(0)
    if ('linked' in options) await expect(page.getByRole('link', { name: 'V2 · 从需求创建独立版本', exact: true })).toBeVisible()
    expect(audit.writes).toHaveLength(0)
    clean(audit)
  })
}
