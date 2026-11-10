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
    if (path === '/api/v1/versions/1/release-batches') return reply({ version_id: 1, version_revision: version.revision, system_id: 1, release_frozen: false, legacy_unrecorded: false, coverage_count: new Set(batches.flatMap(b => b.targets.map((t: any) => t.target_id))).size, items: [...batches].reverse(), total: batches.length, page: 1, page_size: 20 })
    if (path === '/api/v1/versions/1/publish/check') return reply({ passed: true, checks: [{ type: 'R', passed: true, message: '全部需求已验收' }] })
    if (path === '/api/v1/versions/1/publish' || path === '/api/v1/versions/1/release-coverage') {
      const body = route.request().postDataJSON(); writes.push(body)
      const publishing = path.endsWith('/publish')
      expect(publishing ? body.revision : body.version_revision).toBe(version.revision)
      version.revision++
      const b = { id: batches.length + 1, version_id: 1, system_id: 1, kind: publishing ? 'INITIAL' : 'SUPPLEMENT', status: 'COMPLETED', revision: 1, total: body.target_ids.length, completed: body.target_ids.length, created_at: stamp, updated_at: stamp, release_notes: body.release_notes || body.notes || '已发布记录', targets: body.target_ids.map((id: number) => ({ ...targets[id - 1], id: 100 * (batches.length + 1) + id, target_id: id, active: true, completed_at: body.released_at, recorded_at: stamp, completed_by: 1, operator_name: '发布管理员', notes: body.notes, evidence: body.evidence, revision: 1 })) }
      if (body.target_ids.length) batches.push(b)
      if (publishing) { version.status = 'RELEASED'; releases.push({ id: 1, version_id: 1, released_at: body.released_at, result: 'SUCCESS', release_notes: body.release_notes }) }
      return reply(publishing ? { version_id: 1, release: releases[0] } : b, publishing ? 200 : 201)
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
  for (const chooseOnPublish of [true, false]) test(`coverage is optional, later multi-select at ${width}px / selected=${chooseOnPublish}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    const data = await fixture(page)
    data.targets[1].platform = 'PC_WEB'; data.targets[1].name = 'PC 门户 B'
    await page.goto('/#/versions/1')
    await expect(page.getByRole('button', { name: '创建首次发布计划', exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: '发布版本', exact: true }).click()
    const publish = page.getByRole('dialog', { name: '发布版本', exact: true })
    if (chooseOnPublish) await publish.locator('.el-checkbox').filter({ hasText: '小程序 A' }).click()
    await publish.getByRole('textbox', { name: '发布说明', exact: true }).fill('正常发布，可稍后补记覆盖范围')
    await publish.getByRole('button', { name: '确认发布', exact: true }).click()
    await expect(publish).toBeHidden()
    expect(data.version.status).toBe('RELEASED'); expect(data.releases).toHaveLength(1)
    expect(data.batches).toHaveLength(chooseOnPublish ? 1 : 0)
    const original = JSON.stringify(data.releases)
    const panel = page.locator('#release-target-batches')
    await panel.getByRole('button', { name: '补记已发布目标', exact: true }).click()
    const record = page.getByRole('dialog', { name: '补记已发布目标', exact: true })
    if (chooseOnPublish) {
      await expect(record.getByRole('checkbox', { name: /小程序 A/ })).toBeChecked()
      await expect(record.getByRole('checkbox', { name: /小程序 A/ })).toBeDisabled()
    } else await record.locator('.el-checkbox').filter({ hasText: '小程序 A' }).click()
    for (const name of ['PC 门户 B', '小程序 C']) {
      await record.locator('.el-checkbox').filter({ hasText: name }).click()
      await expect(record.getByRole('checkbox', { name: new RegExp(name) })).toBeChecked()
    }
    await page.screenshot({ path: test.info().outputPath(`select-${width}-${chooseOnPublish}.png`), fullPage: true, animations: 'disabled' })
    await record.getByRole('button', { name: '保存已发布目标', exact: true }).click(); await expect(record).toBeHidden()
    await expect(panel).toContainText('已记录 3 个小程序 / PC 目标')
    expect(JSON.stringify(data.releases)).toBe(original)
    expect(data.writes).toHaveLength(2)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    await page.screenshot({ path: test.info().outputPath(`coverage-${width}-${chooseOnPublish}.png`), fullPage: true, animations: 'disabled' })
    await page.goto('/#/releases'); await page.getByText('目标实际记录', { exact: true }).click()
    await expect(page.locator('.record')).toHaveCount(3)
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
