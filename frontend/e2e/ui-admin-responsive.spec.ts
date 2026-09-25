import { expect, test } from '@playwright/test'

const admin = {
  id: 1, username: 'admin', display_name: '系统管理员', email: 'admin@example.com',
  status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'ALL', role_ids: [1],
  permission_codes: ['*'],
}
const role = {
  id: 2, code: 'PROJECT_ADMIN', name: '项目管理员', data_scope: 'ALL',
  enabled: true, is_system: false, revision: 4, permission_ids: [11],
}
const permission = {
  id: 11, code: 'sys.user.view', name: '查看用户', category: 'User', group: '用户管理',
  sensitive: false, deprecated: false, replacement_code: null,
}
const user = {
  id: 7, username: 'project-admin', display_name: '项目负责人',
  email: 'project-admin@example.com', mobile: null, status: 'ACTIVE', revision: 3,
  role_ids: [2],
}
const audit = {
  id: 9, entity_type: 'REQUIREMENT', entity_id: 123, action: 'STATUS_CHANGE',
  operator: { id: 1, username: 'admin', display_name: '系统管理员' },
  before: { status: 'DEVELOPING' }, after: { status: 'DONE' },
  created_at: '2026-09-24T00:00:00Z',
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'admin-test-access')
    localStorage.setItem('iterflow.refresh_token', 'admin-test-refresh')
  })
  await page.route('**/api/v1/**', (route) => {
    const { pathname } = new URL(route.request().url())
    const responses: Record<string, unknown> = {
      '/api/v1/auth/me': admin,
      '/api/v1/audits': { items: [audit], page: 1, size: 20, total: 1 },
      '/api/v1/audits/9': audit,
      '/api/v1/users': { items: [user], page: 1, page_size: 20, total: 1 },
      '/api/v1/roles': [role],
      '/api/v1/roles/permissions': [permission],
    }
    if (!(pathname in responses)) throw new Error(`Unexpected API request: ${pathname}`)
    return route.fulfill({ status: 200, json: responses[pathname] })
  })
})

test('admin lists fit the five release viewports', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  for (const width of [375, 390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    for (const [path, heading, content] of [
      ['/admin/audits', '审计中心', 'STATUS_CHANGE'],
      ['/system/users', '用户管理', '项目负责人'],
      ['/admin/roles', '角色与权限', '项目管理员'],
    ]) {
      await page.goto(path)
      await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible()
      await expect(page.getByText(content, { exact: true }).first()).toBeVisible()
      const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
      expect(scrollWidth, `${path} at ${width}px`).toBeLessThanOrEqual(width + 1)
    }
  }
  expect(errors).toEqual([])
})

test('mobile admin filters and read-only audit detail remain usable', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 900 })
  await page.goto('/admin/audits')
  await expect(page.getByText('STATUS_CHANGE', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '筛选记录' }).click()
  await expect(page.getByRole('heading', { name: '筛选审计记录' })).toBeVisible()
  await expect(page.getByText('时间范围')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(376)
  await page.getByRole('button', { name: '查询' }).click()
  await page.getByRole('button', { name: /REQUIREMENT #123/ }).click()
  await expect(page.getByRole('heading', { name: '审计记录详情' })).toBeVisible()
  await expect(page.getByText('DEVELOPING')).toBeVisible()
})

test('mobile user and role actions open their existing revision-based editors', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 900 })
  await page.goto('/system/users')
  await page.getByRole('button', { name: '配置角色' }).click()
  await expect(page.getByText('已选择 1 / 1 个角色')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(376)
  await page.goto('/admin/roles')
  await page.getByTestId('configure-permissions').click()
  await expect(page.getByText('已选择 1 / 1 项权限')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(376)
})
