import { expect, test, type Page } from '@playwright/test'

const time = '2026-10-01T01:00:00Z'
const release = (id: number) => ({ id, version_id: 456, result: 'SUCCESS', revision: 1, released_at: time, created_at: time, created_by: 8, release_notes: `发布说明 ${id}`, rollback_notes: null })
const version = { id: 456, version_no: 'V1.8.1', name: '已发布验收版本', status: 'RELEASED', revision: 5, owner_id: 1, description: '版本详情说明', released_at: time, created_at: time, updated_at: time, updated_by: 1, planned_release_date: null }

async function fixture(page: Page, permissions = ['rd.release.view', 'rd.version.view'], failure = false) {
  const unexpected: string[] = []
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'drawer-fixture'); localStorage.setItem('iterflow.refresh_token', 'drawer-refresh') })
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url())
    const path = url.pathname.slice('/api/v1'.length)
    const json = (body: unknown, status = 200) => route.fulfill({ status, json: body })
    if (route.request().method() !== 'GET') { unexpected.push(route.request().method() + ' ' + path); return json({}, 500) }
    if (path === '/auth/me') return json({ id: 1, username: 'viewer', display_name: '验收查看者', status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'SELF', role_ids: [], permission_codes: permissions })
    if (path === '/notifications/unread-count') return json({ unread_count: 0 })
    if (path === '/releases') return json({ items: [release(123), release(124)], total: 42, page: 2, page_size: 20 })
    if (path === '/releases/123' || path === '/releases/124') return json(release(Number(path.split('/').at(-1))))
    if (path === '/versions') return json({ items: [version], total: 42, page: 2, page_size: 20 })
    if (path === '/versions/456') return failure ? json({ code: 40400, message: 'private detail' }, 404) : json(version)
    unexpected.push(path)
    return json({}, 500)
  })
  return { unexpected, errors }
}

for (const width of [375, 390, 768, 1280, 1440]) {
  test(`release/version drawer switching, context and expansion at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    const state = await fixture(page)
    const context = '/releases?page=2&version_id=456&date_from=2026-10-01&date_to=2026-10-02'
    await page.goto('/#' + context)
    await page.getByRole('button', { name: '查看详情', exact: true }).first().click()
    let drawer = page.getByRole('dialog', { name: '发布记录详情', exact: true })
    await expect(drawer.getByText('发布说明 123', { exact: true })).toBeVisible()
    await drawer.getByRole('button', { name: '版本 #456', exact: true }).click()
    drawer = page.getByRole('dialog', { name: '版本详情', exact: true })
    await expect(drawer.getByRole('heading', { name: version.name, exact: true })).toBeVisible()
    await expect(drawer.getByRole('heading', { name: '需求清单', exact: true })).toHaveCount(0)
    await drawer.getByRole('button', { name: '查看发布详情', exact: true }).last().click()
    drawer = page.getByRole('dialog', { name: '发布记录详情', exact: true })
    await expect(drawer.getByText('发布说明 124', { exact: true })).toBeVisible()
    await drawer.getByRole('button', { name: '返回上个详情', exact: true }).click()
    drawer = page.getByRole('dialog', { name: '版本详情', exact: true })
    await expect(drawer.getByRole('heading', { name: version.name, exact: true })).toBeVisible()
    await drawer.getByRole('button', { name: '返回上个详情', exact: true }).click()
    drawer = page.getByRole('dialog', { name: '发布记录详情', exact: true })
    await expect(drawer.getByText('发布说明 123', { exact: true })).toBeVisible()
    await expect(page).toHaveURL('/#' + context)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    if (width < 768) {
      const bounds = await drawer.boundingBox()
      expect(bounds?.width).toBe(width)
    }
    await page.screenshot({ path: testInfo.outputPath(`release-drawer-${width}.png`), fullPage: true })
    await drawer.getByRole('button', { name: '关闭详情', exact: true }).click()
    await expect(drawer).not.toBeVisible()
    await expect(page).toHaveURL('/#' + context)
    await page.getByRole('button', { name: '查看版本', exact: true }).first().click()
    drawer = page.getByRole('dialog', { name: '版本详情', exact: true })
    await expect(drawer.getByRole('heading', { name: version.name, exact: true })).toBeVisible()
    await drawer.getByRole('button', { name: '新标签/全屏直达', exact: true }).click()
    await expect(page).toHaveURL('/#/versions/456?return_to=' + encodeURIComponent(context))
    await page.getByRole('link', { name: '返回列表', exact: true }).click()
    await expect(page).toHaveURL('/#' + context)
    expect(state.unexpected).toEqual([])
    expect(state.errors).toEqual([])
  })
}

test('version list and standalone details open release/version drawers without route changes', async ({ page }) => {
  const state = await fixture(page)
  const context = '/versions?page=2&status=RELEASED'
  await page.goto('/#' + context)
  await page.getByText(version.name, { exact: true }).click()
  let drawer = page.getByRole('dialog', { name: '版本详情', exact: true })
  await drawer.getByRole('button', { name: '查看发布详情', exact: true }).first().click()
  drawer = page.getByRole('dialog', { name: '发布记录详情', exact: true })
  await expect(drawer.getByText('发布说明 123', { exact: true })).toBeVisible()
  await expect(page).toHaveURL('/#' + context)
  await drawer.getByRole('button', { name: '新标签/全屏直达', exact: true }).click()
  await expect(page).toHaveURL('/#/releases/123?return_to=' + encodeURIComponent(context))
  await page.getByRole('button', { name: '版本 #456', exact: true }).click()
  drawer = page.getByRole('dialog', { name: '版本详情', exact: true })
  await expect(drawer.getByRole('heading', { name: version.name, exact: true })).toBeVisible()
  await drawer.getByRole('button', { name: '关闭详情', exact: true }).click()
  await page.goto('/#/versions/456')
  await page.getByRole('button', { name: '查看发布详情', exact: true }).first().click()
  drawer = page.getByRole('dialog', { name: '发布记录详情', exact: true })
  await expect(drawer.getByText('发布说明 123', { exact: true })).toBeVisible()
  await expect(page).toHaveURL('/#/versions/456')
  expect(state.unexpected).toEqual([])
  expect(state.errors).toEqual([])
})

test('denied optional version lookup and explicit inaccessible version drawer keep list usable', async ({ page }) => {
  const state = await fixture(page, ['rd.release.view', 'rd.version.view'], true)
  await page.goto('/#/releases')
  await page.getByRole('button', { name: '查看详情', exact: true }).first().click()
  let drawer = page.getByRole('dialog', { name: '发布记录详情', exact: true })
  await expect(drawer.getByText('发布说明 123', { exact: true })).toBeVisible()
  await expect(drawer.getByRole('button', { name: '版本 #456', exact: true })).toHaveCount(0)
  await drawer.getByRole('button', { name: '关闭详情', exact: true }).click()
  await page.getByRole('button', { name: '查看版本', exact: true }).first().click()
  drawer = page.getByRole('dialog', { name: '版本详情', exact: true })
  await expect(drawer.getByRole('alert')).toContainText('版本加载失败')
  await expect(drawer).not.toContainText('private detail')
  await page.keyboard.press('Escape')
  await expect(drawer).not.toBeVisible()
  await expect(page).toHaveURL('/#/releases')
  expect(state.unexpected).toEqual([])
  expect(state.errors).toEqual([])
})
