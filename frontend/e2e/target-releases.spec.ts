import { expect, test, type Page } from '@playwright/test'
import { mockCollaboration } from './collaboration-fixture'

async function fixture(page: Page) {
  const stamp = '2026-11-09T09:00:00Z'
  const version = { id: 1, version_no: 'V-TARGETS', name: '多小程序发布验收版本', revision: 1, status: 'READY', system_id: 1, system_name: '示例业务系统', owner_id: 1, description: '相同版本按目标登记', release_frozen: false, created_at: stamp, updated_at: stamp, released_at: null }
  const targets = ['A', 'B', 'C'].map((code, i) => ({ id: i + 1, system_id: 1, code, name: `小程序 ${code}`, platform: 'WECHAT_MINI_PROGRAM', app_id: `wx${code}`, url: null, enabled: true, revision: 1, created_at: stamp, updated_at: stamp }))
  const batches: any[] = []
  const releases: any[] = []
  const errors: string[] = [], unexpected: string[] = []
  const writes: any[] = []
  page.on('pageerror', e => errors.push(e.message))
  await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'targets-local'); localStorage.setItem('iterflow.refresh_token', 'targets-local') })
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url()), path = url.pathname, method = route.request().method()
    const reply = (data: any, status = 200) => route.fulfill({ status, json: data })
    if (path === '/api/v1/auth/me') return reply({ id: 1, username: 'target-admin', display_name: '发布管理员', status: 'ACTIVE', must_change_password: false, permission_codes: ['*'], data_scope: 'ALL', role_ids: [] })
    if (path === '/api/v1/me/mail-preferences') return reply({ revision: 1, mode: 'TASKS', email: null, verified: false, smtp_enabled: false, notice_acknowledged: true })
    if (path === '/api/v1/notifications/unread-count') return reply({ unread_count: 0 })
    if (path === '/api/v1/systems/manage') return reply({ systems: [{ id: 1, code: 'SYS', name: '示例业务系统', enabled: true, sort_order: 0, revision: 1 }], modules: [] })
    if (path === '/api/v1/systems/1/release-targets') {
      if (method === 'GET') return reply(targets)
      const body = route.request().postDataJSON(); writes.push(body)
      const t = { ...targets[0], ...body, id: targets.length + 1 }; targets.push(t); return reply(t, 201)
    }
    if (path === '/api/v1/versions/1') return reply(version)
    if (path === '/api/v1/versions/1/requirements') return reply({ version_id: 1, items: [], stats: { total: 0, completed: 0, completion_rate: 0, by_status: {} } })
    if (path === '/api/v1/releases') return reply({ items: releases, total: releases.length, page: 1, page_size: 20 })
    if (path === '/api/v1/versions/1/release-targets') return reply(targets.map(t => ({ ...t, covered: batches.some(b => b.targets.some((r: any) => r.target_id === t.id && r.completed_at)), pending: batches.some(b => ['PLANNED', 'IN_PROGRESS'].includes(b.status) && b.targets.some((r: any) => r.target_id === t.id && !r.completed_at)) })))
    if (path === '/api/v1/versions/1/release-batches') {
      if (method === 'GET') return reply({ version_id: 1, version_revision: version.revision, system_id: 1, release_frozen: version.release_frozen, legacy_unrecorded: false, coverage_count: new Set(batches.flatMap(b => b.targets.filter((t: any) => t.completed_at).map((t: any) => t.target_id))).size, items: [...batches].reverse(), total: batches.length, page: 1, page_size: 20 })
      const body = route.request().postDataJSON(); writes.push(body); expect(body.version_revision).toBe(version.revision)
      version.revision++
      const b = { ...body, id: batches.length + 1, version_id: 1, system_id: 1, status: 'PLANNED', revision: 1, total: body.target_ids.length, completed: 0, created_at: stamp, updated_at: stamp, targets: body.target_ids.map((id: number) => ({ ...targets[id - 1], id: 100 * (batches.length + 1) + id, target_id: id, active: true, completed_at: null, recorded_at: null, completed_by: null, operator_name: null, notes: null, evidence: null, revision: 1 })) }
      batches.push(b); return reply(b, 201)
    }
    const completion = path.match(/release-batches\/(\d+)\/targets\/(\d+)\/complete$/)
    if (completion) {
      const body = route.request().postDataJSON(); writes.push(body)
      const b = batches.find(b => b.id === Number(completion[1])), t = b.targets.find((t: any) => t.id === Number(completion[2]))
      expect(body).toMatchObject({ version_revision: version.revision, batch_revision: b.revision, revision: t.revision })
      Object.assign(t, { completed_at: body.released_at, recorded_at: stamp, completed_by: 1, operator_name: '发布管理员', notes: body.notes, evidence: body.evidence, revision: t.revision + 1 })
      b.completed++; b.revision++; b.status = b.completed === b.total ? 'COMPLETED' : 'IN_PROGRESS'; version.revision++
      if (b.kind === 'INITIAL') { version.release_frozen = true; if (b.status === 'COMPLETED') { version.status = 'RELEASED'; releases.push({ id: 1, version_id: 1, released_at: body.released_at, result: 'SUCCESS', release_notes: b.release_notes }) } }
      return reply(b)
    }
    if (path === '/api/v1/target-release-records') {
      let rows = batches.flatMap(b => b.targets.filter((t: any) => t.completed_at).map((t: any) => ({ ...t, version_id: 1, version_no: version.version_no, version_name: version.name, system_id: 1, batch_id: b.id, batch_kind: b.kind })))
      if (url.searchParams.has('target_id')) rows = rows.filter(r => r.target_id === Number(url.searchParams.get('target_id')))
      return reply({ items: rows, total: rows.length, page: 1, page_size: 20 })
    }
    if (path === '/api/v1/target-release-records/options') return reply(targets.map(t => ({ id: t.id, label: t.name })))
    if (await mockCollaboration(route)) return
    unexpected.push(`${method} ${path}`); return reply({ message: 'Unexpected request' }, 500)
  })
  return { version, targets, batches, releases, errors, unexpected, writes }
}

for (const width of [1440, 375]) {
  test(`initial coverage and later supplement at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    const data = await fixture(page)
    await page.goto('/#/versions/1')
    await page.getByRole('button', { name: '创建首次发布计划', exact: true }).click()
    const plan = page.getByRole('dialog', { name: '创建发布计划', exact: true })
    await plan.locator('.el-checkbox').filter({ hasText: '小程序 A' }).click()
    await expect(plan.getByRole('checkbox', { name: /小程序 A/ })).toBeChecked()
    await plan.locator('.el-checkbox').filter({ hasText: '小程序 B' }).click()
    await plan.getByText('本批发布说明', { exact: true }).click()
    await plan.locator('textarea').fill('首次覆盖两个小程序')
    await plan.getByRole('button', { name: '确认计划', exact: true }).click()
    await expect(plan).toBeHidden()
    const panel = page.locator('#release-target-batches')
    await expect(panel).toContainText('未开始 · 0/2')
    const completion = page.getByRole('dialog', { name: '登记目标实际上线', exact: true })
    for (const target of ['A', 'B']) {
      await panel.getByRole('button', { name: `登记 小程序 ${target} 实际上线`, exact: true }).click()
      await completion.getByRole('button', { name: '确认实际已上线', exact: true }).click()
      await expect(completion).toBeHidden()
      if (target === 'A') {
        await expect(panel).toContainText('进行中 · 1/2')
        expect(data.version.status).toBe('READY'); expect(data.releases).toHaveLength(0)
        await expect(page.getByRole('button', { name: '添加需求', exact: true })).toHaveCount(0)
        await page.screenshot({ path: test.info().outputPath(`partial-${width}.png`), fullPage: true })
      }
    }
    await expect(panel).toContainText('已完成 · 2/2'); expect(data.releases).toHaveLength(1)
    await panel.getByRole('button', { name: '新增补发 / 重新发布', exact: true }).click()
    await plan.locator('.el-checkbox').filter({ hasText: '小程序 C' }).click()
    await plan.getByText('本批发布说明', { exact: true }).click(); await plan.locator('textarea').fill('隔周补发新小程序')
    await plan.getByRole('button', { name: '确认计划', exact: true }).click(); await expect(plan).toBeHidden()
    await panel.getByRole('button', { name: '登记 小程序 C 实际上线', exact: true }).click()
    await completion.getByRole('button', { name: '确认实际已上线', exact: true }).click(); await expect(completion).toBeHidden()
    await expect(panel).toContainText('累计覆盖 3 个目标'); expect(data.releases).toHaveLength(1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    await page.goto('/#/releases'); await page.getByText('目标实际记录', { exact: true }).click()
    await expect(page.locator('.record')).toHaveCount(3)
    await page.screenshot({ path: test.info().outputPath(`records-${width}.png`), fullPage: true })
    expect(data.errors).toEqual([]); expect(data.unexpected).toEqual([])
  })
  test(`system release-target directory at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    const data = await fixture(page)
    await page.goto('/#/admin/systems')
    await page.getByRole('button', { name: '发布目标', exact: true }).click()
    await page.getByRole('button', { name: '新增发布目标', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '新增发布目标', exact: true })
    await dialog.getByRole('textbox', { name: '目标名称' }).fill('小程序 D')
    await dialog.getByRole('textbox', { name: '目标编码' }).fill('D')
    await dialog.getByRole('button', { name: '保存目标', exact: true }).click()
    await expect(dialog).toBeHidden(); expect(data.targets).toHaveLength(4)
    await expect(page.getByRole('dialog', { name: '管理发布目标', exact: true })).toContainText('小程序 D')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    expect(data.errors).toEqual([]); expect(data.unexpected).toEqual([])
  })
}
