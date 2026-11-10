import { mockCollaboration } from './collaboration-fixture'
import { expect, test } from '@playwright/test'

type CatalogItem = {
  id: number
  code: string
  name: string
  enabled: boolean
  sort_order: number
  revision: number
  created_at: string
  created_by: number
  updated_at: string
  updated_by: number
}
type ModuleItem = CatalogItem & { system_id: number }

for (const width of [1440, 375]) {
  test(`administrator manages systems with module controls hidden at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const systems: CatalogItem[] = []
    const modules: ModuleItem[] = []
    const timestamp = '2026-09-26T00:00:00Z'
    await page.addInitScript(() => {
      localStorage.setItem('iterflow.access_token', 'catalog-test-access')
      localStorage.setItem('iterflow.refresh_token', 'catalog-test-refresh')
    })
    await page.route('**/api/v1/**', async (route) => {
      if (await mockCollaboration(route)) return
      const { pathname } = new URL(route.request().url())
      if (pathname === '/api/v1/notifications/unread-count') return route.fulfill({ status: 200, json: { unread_count: 0 } })
      const method = route.request().method()
      if (pathname === '/api/v1/auth/me') {
        return route.fulfill({ status: 200, json: {
          id: 1, username: 'admin', display_name: '系统管理员', email: null,
          status: 'ACTIVE', revision: 1, must_change_password: false,
          data_scope: 'ALL', role_ids: [1],
          permission_codes: ['sys.system.manage', 'rd.feedback.create', 'rd.feedback.view'],
        } })
      }
      if (pathname === '/api/v1/systems/manage' && method === 'GET') {
        return route.fulfill({ status: 200, json: { systems, modules } })
      }
      if (pathname === '/api/v1/systems' && method === 'GET') {
        const activeSystems = systems.filter((item) => item.enabled)
        return route.fulfill({ status: 200, json: {
          systems: activeSystems,
          modules: modules.filter((item) => item.enabled && activeSystems.some((system) => system.id === item.system_id)),
        } })
      }
      if (pathname === '/api/v1/systems' && method === 'POST') {
        const body = route.request().postDataJSON()
        const item: CatalogItem = {
          ...body, id: systems.length + 1, revision: 1,
          created_at: timestamp, created_by: 1, updated_at: timestamp, updated_by: 1,
        }
        systems.push(item)
        return route.fulfill({ status: 201, json: item })
      }
      if (pathname === '/api/v1/systems/1' && method === 'PATCH') {
        const body = route.request().postDataJSON()
        const system = systems[0]
        if (body.revision !== system.revision) {
          return route.fulfill({ status: 409, json: { code: 40910, message: '编辑冲突', data: { current_revision: system.revision } } })
        }
        Object.assign(system, body, { revision: system.revision + 1, updated_at: timestamp })
        return route.fulfill({ status: 200, json: system })
      }
      throw new Error(`Unexpected API request: ${method} ${pathname}`)
    })

    await page.goto('/#/admin/systems')
    await expect(page.getByRole('heading', { name: '业务系统', level: 1, exact: true })).toBeVisible()
    await page.getByRole('button', { name: '创建系统' }).click()
    let dialog = page.getByRole('dialog')
    await dialog.getByPlaceholder('如 ITERFLOW').fill('ITERFLOW')
    await dialog.getByPlaceholder('输入名称').fill('迭程')
    await dialog.getByRole('button', { name: '保存' }).click()
    await expect(page.getByRole('button', { name: '编辑系统 迭程' })).toBeVisible()

    await expect(page.getByRole('dialog')).toHaveCount(0)
    await expect(page.getByRole('button', { name: /模块/ })).toHaveCount(0)
    await expect(page.getByRole('columnheader', { name: '模块', exact: true })).toHaveCount(0)
    // Historical module rows remain, but neither management nor feedback exposes selectors.
    modules.push({ ...systems[0], id: 1, system_id: 1, code: 'FEEDBACK', name: '反馈中心' })
    await page.reload()
    await expect(page.getByRole('button', { name: '编辑系统 迭程' })).toBeVisible()
    await expect(page.getByText('个模块', { exact: false })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /模块/ })).toHaveCount(0)
    await page.screenshot({ path: `test-results/system-catalog-${width}.png`, fullPage: true })

    await page.goto('/#/feedbacks/new')
    const systemSelect = page.locator('.el-form-item').filter({ hasText: '所属系统' }).locator('.el-select')
    await systemSelect.click()
    await expect(page.getByRole('option', { name: '迭程' })).toBeVisible()
    await page.getByRole('option', { name: '迭程' }).click()
    await expect(page.locator('.el-form-item').filter({ hasText: '所属模块' })).toHaveCount(0)
    expect(modules).toHaveLength(1)

    await page.goto('/#/admin/systems')
    await page.getByRole('button', { name: '编辑系统 迭程' }).click()
    dialog = page.getByRole('dialog')
    await dialog.locator('.el-switch').click()
    await dialog.getByRole('button', { name: '保存' }).click()
    await page.goto('/#/feedbacks/new')
    await systemSelect.click()
    await expect(page.getByRole('option', { name: '迭程' })).toHaveCount(0)
  })
}
