import { expect, test } from '@playwright/test'

const schema = {
  info: { title: '迭程 IterFlow 接口文档', version: '1.8.1' },
  paths: {
    '/api/v1/auth/login': { post: { summary: '登录', tags: ['Auth'], responses: { '200': { description: 'Successful Response' } } } },
    '/api/v1/feedbacks': { post: {
      summary: '提交反馈', tags: ['Feedback'], security: [{ bearerAuth: [] }],
      requestBody: { required: true, content: { 'application/json': { schema: { $ref: '#/components/schemas/FeedbackCreate' } } } },
      responses: { '200': { description: 'Successful Response', content: { 'application/json': { schema: { $ref: '#/components/schemas/FeedbackPage' } } } } },
    } },
  },
  components: { schemas: { FeedbackCreate: { type: 'object', required: ['title'], properties: {
    title: { type: 'string', description: '反馈标题' },
    urgency: { type: 'string', enum: ['NORMAL', 'URGENT'] },
  } }, FeedbackPage: { type: 'object', properties: {
    items: { title: '数据列表', type: 'array', items: { $ref: '#/components/schemas/FeedbackOut' } },
    total: { title: '总条数', type: 'integer' },
  } }, FeedbackOut: { type: 'object', properties: {
    feedback_no: { title: '反馈编号', type: 'string' },
    status: { title: '反馈状态', type: 'string', enum: ['NEW', 'ACCEPTED'] },
  } } } },
}

for (const width of [375, 1440]) {
  for (const allowed of [true, false]) {
    test(`documentation menu and route honor role eligibility at ${width}px (allowed=${allowed})`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      let docsReads = 0
      await page.addInitScript(() => {
        localStorage.setItem('iterflow.access_token', 'docs-access')
        localStorage.setItem('iterflow.refresh_token', 'docs-refresh')
      })
      await page.route('**/api/v1/**', route => {
        const path = new URL(route.request().url()).pathname
        if (path === '/api/v1/auth/me') return route.fulfill({ json: {
          id: 1, username: 'docs-user', display_name: '文档用户', email: null, status: 'ACTIVE',
          revision: 1, role_ids: [1], permission_codes: ['*'], data_scope: 'SELF',
          must_change_password: false, can_view_api_docs: allowed,
        } })
        if (path === '/api/v1/notifications/unread-count') return route.fulfill({ json: { unread_count: 0 } })
        if (path === '/api/v1/docs/openapi') {
          docsReads++
          expect(route.request().headers().authorization).toBe('Bearer docs-access')
          return route.fulfill({ status: allowed ? 200 : 403, json: allowed ? schema : { code: 40300, message: '禁止访问', data: null } })
        }
        return route.fulfill({ status: 404, json: {} })
      })
      await page.goto('/#/profile')
      await expect(page.getByRole('heading', { name: '个人中心', exact: true })).toBeVisible()
      if (allowed) {
        await page.getByRole('button', { name: '接口文档', exact: true }).click()
        await expect(page.getByRole('heading', { name: '接口文档', exact: true })).toBeVisible()
        await page.getByRole('textbox', { name: '搜索接口', exact: true }).fill('提交反馈')
        await page.getByText('提交反馈', { exact: true }).click()
        await expect(page.getByText('反馈标题', { exact: true })).toBeVisible()
        await expect(page.getByText('可选值：NORMAL、URGENT', { exact: true })).toBeVisible()
        await expect(page.getByText('数据列表', { exact: true })).toBeVisible()
        await expect(page.getByText('总条数', { exact: true })).toBeVisible()
        await page.getByText('查看子字段', { exact: true }).click()
        await expect(page.getByText('反馈编号', { exact: true })).toBeVisible()
        await expect(page.getByText('反馈状态', { exact: true })).toBeVisible()
        const download = page.waitForEvent('download')
        await page.getByRole('button', { name: '下载 OpenAPI', exact: true }).click()
        expect((await download).suggestedFilename()).toBe('iterflow-openapi.json')
        expect(docsReads).toBe(1)
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
      } else {
        await expect(page.getByRole('button', { name: '接口文档', exact: true })).toHaveCount(0)
        await expect(page.getByRole('link', { name: '接口文档', exact: true })).toHaveCount(0)
        await page.goto('/#/admin/api-docs')
        await expect(page).toHaveURL(/#\/forbidden$/)
        expect(docsReads).toBe(0)
      }
    })
  }
}

test('backend denial after role revocation leaves no schema visible', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'docs-access')
    localStorage.setItem('iterflow.refresh_token', 'docs-refresh')
  })
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/v1/auth/me') return route.fulfill({ json: { id: 1, username: 'docs-user', status: 'ACTIVE', revision: 1, permission_codes: [], data_scope: 'SELF', must_change_password: false, can_view_api_docs: true } })
    if (path === '/api/v1/notifications/unread-count') return route.fulfill({ json: { unread_count: 0 } })
    return route.fulfill({ status: 403, json: { code: 40300, message: '文档资格已撤销', data: null } })
  })
  await page.goto('/#/admin/api-docs')
  await expect(page.getByRole('heading', { name: '接口文档不可访问', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '下载 OpenAPI', exact: true })).toBeDisabled()
  await expect(page.getByText('/api/v1/auth/login', { exact: true })).toHaveCount(0)
})
