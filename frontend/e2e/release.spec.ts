import { expect, test } from '@playwright/test'

test('production Web login, first password change and feedback creation', async ({ page }) => {
  const username = process.env.INIT_ADMIN_USERNAME
  const initialPassword = process.env.INIT_ADMIN_PASSWORD
  const newPassword = process.env.ITERFLOW_BROWSER_NEW_PASSWORD
  if (!username || !initialPassword || !newPassword) {
    throw new Error('CI browser credentials are required')
  }
  const browserErrors: string[] = []
  page.on('pageerror', (error) => browserErrors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text())
  })

  await page.goto('/')
  await expect(page.getByRole('heading', { name: '迭程 IterFlow' })).toBeVisible()
  await page.getByPlaceholder('用户名').fill(username)
  await page.getByPlaceholder('密码').fill(initialPassword)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '修改初始密码' })).toBeVisible()
  await page.locator('input[type="password"]').nth(0).fill(initialPassword)
  await page.locator('input[type="password"]').nth(1).fill(newPassword)
  await page.locator('input[type="password"]').nth(2).fill(newPassword)
  await page.getByRole('button', { name: '保存新密码' }).click()
  await expect(page.getByRole('heading', { name: '首页 / 系统概览' })).toBeVisible()

  await page.goto('/feedbacks')
  await expect(page.getByRole('heading', { name: '反馈中心' })).toBeVisible()
  await page.goto('/feedbacks/new')
  const title = `发布验收反馈-${Date.now()}`
  await page.locator('.el-form-item').filter({ hasText: '标题' }).locator('input').fill(title)
  await page.locator('.el-form-item').filter({ hasText: '详细描述' }).locator('textarea').fill('生产构建浏览器验收反馈')
  await page.getByRole('button', { name: '提交', exact: true }).click()
  await expect(page).toHaveURL(/\/feedbacks\/\d+$/)
  await page.goto('/feedbacks')
  await expect(page.getByText(title)).toBeVisible()
  expect(browserErrors).toEqual([])
})
