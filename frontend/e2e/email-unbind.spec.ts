import { expect, test, type Page } from '@playwright/test'

async function setup(page: Page, pendingOnly = false) {
  let preferences = { revision: 5, mode: 'ALL', email: pendingOnly ? null : 'old@example.test', verified: !pendingOnly, pending_email: 'pending@example.test', smtp_enabled: true, notice_acknowledged: true }
  const writes: number[] = []
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'unbind-test-token')
    localStorage.setItem('iterflow.refresh_token', 'unbind-test-refresh')
  })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/v1/auth/me') return route.fulfill({ json: { id: 15, username: 'unbind-member', display_name: '解绑验收成员', email: preferences.email, revision: 1, status: 'ACTIVE', must_change_password: false, data_scope: 'SELF', role_ids: [], permission_codes: [] } })
    if (path === '/api/v1/me/mail-preferences') return route.fulfill({ json: preferences })
    if (path === '/api/v1/notifications/unread-count') return route.fulfill({ json: { unread_count: 0 } })
    if (path === '/api/v1/me/email-unbind') {
      expect(route.request().method()).toBe('POST')
      const { revision } = route.request().postDataJSON(); writes.push(revision)
      expect(Object.keys(route.request().postDataJSON())).toEqual(['revision'])
      if (revision !== preferences.revision) return route.fulfill({ status: 409, json: { code: 40910, message: '邮件设置已修改, 请刷新' } })
      preferences = { ...preferences, revision: preferences.revision + 1, email: null, pending_email: null, verified: false }
      return route.fulfill({ json: preferences })
    }
    throw new Error(`Unexpected request ${route.request().method()} ${path}`)
  })
  return { writes, change: () => { preferences = { ...preferences, revision: 6, email: 'changed@example.test' } }, read: () => preferences }
}

for (const width of [375, 768, 1440]) {
  for (const pendingOnly of [false, true]) {
    test(`unbind confirmation, profile and verification at ${width}, pendingOnly=${pendingOnly}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      const server = await setup(page, pendingOnly)
      await page.goto('/#/profile')
      await page.getByRole('button', { name: '取消绑定', exact: true }).click()
      const dialog = page.getByRole('dialog', { name: '取消绑定通知邮箱', exact: true })
      await expect(dialog).toContainText('未完成的验证码也会失效')
      expect(server.writes).toEqual([])
      await dialog.getByRole('button', { name: '暂不取消' }).click()
      await expect(dialog).toBeHidden()
      expect(server.writes).toEqual([])
      await page.getByRole('button', { name: '取消绑定', exact: true }).click()
      await expect(dialog).toBeVisible()
      const bounds = await dialog.boundingBox()
      expect(bounds!.x).toBeGreaterThanOrEqual(0)
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width)
      if (width === 375) {
        const height = await dialog.getByRole('button', { name: '确认取消绑定' }).evaluate(el => el.getBoundingClientRect().height)
        expect(height).toBeGreaterThanOrEqual(44)
      }
      await page.screenshot({ path: `test-results/email-unbind-${width}-${pendingOnly}.png` })
      await dialog.getByRole('button', { name: '确认取消绑定' }).click()
      await expect(dialog).toBeHidden()
      await expect(page.getByText('通知邮箱已取消绑定，站内通知仍可正常使用。')).toBeVisible()
      await expect(page.getByRole('button', { name: '取消绑定', exact: true })).toHaveCount(0)
      await expect(page.getByRole('textbox', { name: '通知邮箱', exact: true })).toHaveValue('')
      await expect(page.getByRole('button', { name: '发送验证码', exact: true })).toBeDisabled()
      await expect(page.getByText('old@example.test', { exact: true })).toHaveCount(0)
      expect(server.writes).toEqual([5])
      expect(server.read()).toMatchObject({ mode: 'ALL', notice_acknowledged: true, email: null, pending_email: null, verified: false })
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
      await page.reload()
      await expect(page.getByRole('button', { name: '取消绑定', exact: true })).toHaveCount(0)
      await expect(page.getByRole('textbox', { name: '通知邮箱', exact: true })).toHaveValue('')
      expect(server.writes).toEqual([5])
    })
  }
}

test('cross-device stale settings require refresh and a new explicit confirmation', async ({ page }) => {
  const server = await setup(page)
  await page.goto('/#/profile')
  await page.getByRole('button', { name: '取消绑定', exact: true }).click()
  server.change()
  const dialog = page.getByRole('dialog', { name: '取消绑定通知邮箱', exact: true })
  await dialog.getByRole('button', { name: '确认取消绑定' }).click()
  await expect(dialog.getByRole('alert')).toContainText('邮件设置已修改')
  expect(server.writes).toEqual([5])
  await dialog.getByRole('button', { name: '刷新设置' }).click()
  await expect(dialog).toBeHidden()
  await expect(page.getByText('当前邮箱：changed@example.test', { exact: false })).toBeVisible()
  expect(server.writes).toEqual([5])
  await page.getByRole('button', { name: '取消绑定', exact: true }).click()
  await dialog.getByRole('button', { name: '确认取消绑定' }).click()
  await expect(dialog).toBeHidden()
  expect(server.writes).toEqual([5, 6])
})

test('failed unbind keeps the address and confirmation instead of claiming success', async ({ page }) => {
  await setup(page)
  await page.route('**/api/v1/me/email-unbind', route => route.fulfill({ status: 503, json: { message: 'Unavailable' } }))
  await page.goto('/#/profile')
  await page.getByRole('button', { name: '取消绑定', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '取消绑定通知邮箱', exact: true })
  await dialog.getByRole('button', { name: '确认取消绑定' }).click()
  await expect(dialog.getByRole('alert')).toContainText('操作未完成')
  await expect(page.getByText('当前邮箱：old@example.test', { exact: false })).toBeVisible()
  await expect(page.getByText('通知邮箱已取消绑定，站内通知仍可正常使用。')).toHaveCount(0)
})
