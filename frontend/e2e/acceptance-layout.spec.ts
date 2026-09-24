import { expect, test } from '@playwright/test'

test('V1.5 login remains usable at all release viewports', async ({ page }) => {
  for (const width of [375, 390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: '迭程 IterFlow' })).toBeVisible()
    await expect(page.getByPlaceholder('用户名')).toBeVisible()
    await expect(page.getByPlaceholder('密码')).toBeVisible()
    await expect(page.getByRole('button', { name: '登录' })).toBeVisible()
    const widthUsed = await page.evaluate(() => document.documentElement.scrollWidth)
    expect(widthUsed, `${width}px login overflow`).toBeLessThanOrEqual(width + 1)
  }
})
