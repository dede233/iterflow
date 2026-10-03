import { expect, test, type Page } from '@playwright/test'

const release = {
  id: 123, version_id: 456, result: 'SUCCESS', revision: 1, created_by: 8,
  released_at: '2026-10-01T01:00:00Z', created_at: '2026-10-01T02:00:00Z',
  release_notes: '完整发布说明\nhttps://example.com/' + 'release-path'.repeat(100),
  rollback_notes: '历史回滚说明\n' + 'rollback-information'.repeat(100),
}

async function fixture(page: Page, options: { version?: boolean; releasePermission?: boolean; notification?: boolean; versionFailure?: boolean } = {}) {
  const state = { reads: 0, releaseRequests: 0, versionRequests: 0, beforeRead: false, count: 2 }
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'release-detail-access')
    localStorage.setItem('iterflow.refresh_token', 'release-detail-refresh')
  })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown, status = 200) => route.fulfill({ status, json: body })
    if (path === '/api/v1/auth/me') return json({ id: 1, username: 'viewer', display_name: '发布记录查看者', email: null, status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'SELF', role_ids: [], permission_codes: [...(options.releasePermission === false ? [] : ['rd.release.view']), ...(options.version ? ['rd.version.view'] : [])] })
    if (path === '/api/v1/notifications/unread-count') return json({ unread_count: state.count })
    if (path === '/api/v1/notifications') return json([{ id: 1, type: 'RELEASE', title: '发布记录通知', content: '查看实际发布记录', entity_type: 'RELEASE', entity_id: 123, read_at: null, created_at: '2026-10-01T00:00:00Z' }])
    if (path === '/api/v1/notifications/1/read') {
      state.reads++
      state.count--
      return json({ ok: true })
    }
    if (path === '/api/v1/releases') return json({ total: 1, page: 1, page_size: 20, items: [release] })
    if (path === '/api/v1/releases/123') {
      state.releaseRequests++
      if (options.notification && !state.reads) state.beforeRead = true
      return json(release)
    }
    if (path === '/api/v1/versions/456') {
      state.versionRequests++
      if (options.versionFailure) return json({ code: 40400, message: '版本不存在' }, 404)
      return json({ id: 456, version_no: 'V1.6.0', name: 'long-version-name'.repeat(100) })
    }
    throw new Error(`Unexpected request: ${path}`)
  })
  return state
}

for (const width of [375, 390, 768, 1280, 1440]) {
  for (const version of [false, true]) {
    test(`release list to read-only detail fits ${width}px, version permission=${version}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      const state = await fixture(page, { version })
      await page.goto('/#/releases')
      await expect(page.getByRole('button', { name: '查看详情', exact: true })).toBeVisible()
      await expect(page.getByRole('button', { name: '查看版本', exact: true })).toHaveCount(version ? 1 : 0)
      await page.getByRole('button', { name: '查看详情', exact: true }).click()
      await expect(page).toHaveURL(/\/#\/releases\/123\?return_to=%2Freleases$/)
      await expect(page.getByRole('heading', { name: '发布记录详情', exact: true })).toBeVisible()
      await expect(page.getByText('用户 #8', { exact: true })).toBeVisible()
      await expect(page.locator('.release-notes').nth(0)).toHaveText(release.release_notes)
      await expect(page.locator('.release-notes').nth(1)).toHaveText(release.rollback_notes)
      await expect(page.getByRole('link', { name: '版本 #456', exact: true })).toHaveCount(version ? 1 : 0)
      if (version) await expect(page.locator('.version-label')).toContainText('V1.6.0 · long-version-name')
      expect(state.versionRequests).toBe(version ? 1 : 0)
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
      const escaping = await page.locator('.release-detail .section-card, .release-detail .release-notes, .release-detail .version-label').evaluateAll(nodes => nodes.filter(node => node.scrollWidth > node.clientWidth + 1).length)
      expect(escaping).toBe(0)
      await expect(page.locator('.release-detail button')).toHaveCount(0)
    })
  }
}

test('release notification reads and updates badge before entering the record ID detail', async ({ page }) => {
  const state = await fixture(page, { notification: true })
  await page.goto('/#/notifications')
  await expect(page.getByText('2 条未读', { exact: true })).toBeVisible()
  await page.locator('.notification-card').click()
  await expect(page).toHaveURL(/\/#\/releases\/123$/)
  await expect(page.getByText('用户 #8', { exact: true })).toBeVisible()
  await expect(page.locator('aside .notification-badge')).toHaveText('1')
  expect(state.reads).toBe(1)
  expect(state.beforeRead).toBe(false)
  expect(state.releaseRequests).toBe(1)
  expect(state.versionRequests).toBe(0)
})

test('release notification cannot bypass revoked release permission', async ({ page }) => {
  const state = await fixture(page, { notification: true, releasePermission: false })
  await page.goto('/#/notifications')
  await expect(page.getByText('2 条未读', { exact: true })).toBeVisible()
  await page.locator('.notification-card').click()
  await expect(page).toHaveURL(/\/#\/forbidden$/)
  expect(state.reads).toBe(1)
  expect(state.count).toBe(1)
  expect(state.releaseRequests).toBe(0)
})

test('direct detail navigation requires release permission', async ({ page }) => {
  const state = await fixture(page, { releasePermission: false })
  await page.goto('/#/releases/123')
  await expect(page).toHaveURL(/\/#\/forbidden$/)
  expect(state.releaseRequests).toBe(0)
})

test('optional version lookup failure keeps the release detail usable', async ({ page }) => {
  const state = await fixture(page, { version: true, versionFailure: true })
  await page.goto('/#/releases/123')
  await expect(page.getByText('用户 #8', { exact: true })).toBeVisible()
  await expect(page.getByText('版本 #456', { exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: '版本 #456', exact: true })).toHaveCount(0)
  await expect(page.locator('.release-notes').first()).toHaveText(release.release_notes)
  await expect(page.locator('[role="alert"]')).toHaveCount(0)
  expect(state.versionRequests).toBe(1)
})
