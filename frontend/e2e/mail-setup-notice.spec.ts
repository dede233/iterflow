import { mockReadPanels } from './collaboration-fixture'
import { expect, test, type Page } from '@playwright/test'

const base = { revision: 1, mode: 'TASKS', email: null, verified: false, pending_email: null, smtp_enabled: true, notice_acknowledged: false }
async function setup(page: Page, overrides = {}) {
  let preferences = { ...base, ...overrides }
  let acknowledgements = 0
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'notice-test-token')
    localStorage.setItem('iterflow.refresh_token', 'notice-test-refresh')
  })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/v1/auth/me') return route.fulfill({ json: {
      id: 15, username: 'notice-member', display_name: '普通成员', email: null, revision: 1, status: 'ACTIVE',
      must_change_password: false, data_scope: 'SELF', role_ids: [], permission_codes: [],
    } })
    if (path === '/api/v1/me/mail-preferences') return route.fulfill({ json: preferences })
    if (path === '/api/v1/me/mail-notice/acknowledge') {
      expect(route.request().method()).toBe('POST')
      expect(route.request().postDataJSON()).toEqual({ revision: preferences.revision })
      acknowledgements++
      preferences = { ...preferences, revision: preferences.revision + 1, notice_acknowledged: true }
      return route.fulfill({ json: preferences })
    }
    if (path === '/api/v1/notifications') return route.fulfill({ json: [] })
    if (path === '/api/v1/notifications/unread-count') return route.fulfill({ json: { unread_count: 0 } })
    if (await mockReadPanels(route)) return
    throw new Error(`Unexpected API request: ${route.request().method()} ${path}`)
  })
  return () => acknowledgements
}

test('notice fits five viewports, saves acknowledgement and stays hidden after refresh', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  const writes = await setup(page)
  for (const width of [375, 390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/notifications')
    await page.reload()
    const dialog = page.getByRole('dialog', { name: '邮件通知已上线' })
    await expect(dialog).toBeVisible()
    await dialog.evaluate(async el => {
      const overlay = el.closest('.el-overlay')!
      await Promise.all(overlay.getAnimations({ subtree: true }).map(animation => animation.finished))
    })
    const bounds = await dialog.boundingBox()
    expect(bounds!.x).toBeGreaterThanOrEqual(0)
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width)
    const [ack, bind] = await dialog.locator('.notice-actions button').evaluateAll(buttons => buttons.map(button => {
      const { x, y, width, height } = button.getBoundingClientRect()
      return { x, y, width, height }
    }))
    expect(ack!.y).toBe(bind!.y)
    if (width < 768) expect(ack!.height).toBeGreaterThanOrEqual(44)
    await page.screenshot({ path: `test-results/mail-notice-${width}.png` })
  }
  await page.getByRole('button', { name: '我已知晓' }).click()
  await expect(page.getByRole('dialog')).toBeHidden()
  expect(writes()).toBe(1)
  await page.reload()
  await expect(page.getByRole('heading', { name: '通知中心' })).toBeVisible()
  await expect(page.getByRole('dialog')).toBeHidden()
  expect(errors).toEqual([])
})

test('unverified users can jump to the mail settings section without sending anything', async ({ page }) => {
  const writes = await setup(page, { pending_email: 'pending@example.test' })
  await page.goto('/#/notifications')
  await expect(page.getByText('你的通知邮箱尚未完成验证。', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: '去验证邮箱' }).click()
  await expect(page).toHaveURL(/profile#mail-notifications$/)
  await expect(page.getByRole('heading', { name: '邮件通知', exact: true })).toBeInViewport()
  await expect(page.getByRole('dialog')).toBeHidden()
  expect(writes()).toBe(0)
})

for (const state of [{ verified: true }, { notice_acknowledged: true }, { mode: 'OFF' }, { smtp_enabled: false }]) {
  test(`does not prompt for ${JSON.stringify(state)}`, async ({ page }) => {
    await setup(page, state)
    const read = page.waitForResponse('**/api/v1/me/mail-preferences')
    await page.goto('/#/notifications'); await read
    await expect(page.getByRole('heading', { name: '通知中心' })).toBeVisible()
    await expect(page.getByRole('dialog')).toBeHidden()
  })
}

test('profile access is not interrupted and closing is not permanent acknowledgement', async ({ page }) => {
  const writes = await setup(page)
  await page.goto('/#/profile')
  await expect(page.getByRole('heading', { name: '邮件通知', exact: true })).toBeVisible()
  await expect(page.getByRole('dialog')).toBeHidden()
  await page.goto('/#/notifications')
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toBeHidden()
  expect(writes()).toBe(0)
  await page.reload()
  await expect(page.getByRole('dialog')).toBeVisible()
})

test('failed saves leave the notice open with an actionable error', async ({ page }) => {
  await setup(page)
  await page.route('**/api/v1/me/mail-notice/acknowledge', route => route.fulfill({ status: 500, json: { message: 'Unavailable' } }))
  await page.goto('/#/notifications')
  await page.getByRole('button', { name: '我已知晓' }).click()
  await expect(page.getByRole('alert')).toContainText('未能保存知晓状态')
  await expect(page.getByRole('button', { name: '我已知晓' })).toBeEnabled()
  await page.reload()
  await expect(page.getByRole('dialog')).toBeVisible()
})
