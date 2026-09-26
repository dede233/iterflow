import { expect, test } from '@playwright/test'

test('a MEMBER opens the published feedback from its notification after marking it read', async ({ page }) => {
  const pageErrors: string[] = []
  const readRequests: number[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'member-access-token')
    localStorage.setItem('iterflow.refresh_token', 'member-refresh-token')
  })

  await page.route('**/api/v1/**', async (route) => {
    const { pathname } = new URL(route.request().url())
    const method = route.request().method()
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })

    if (pathname === '/api/v1/auth/me' && method === 'GET') {
      return json({
        id: 7,
        username: 'member',
        display_name: '普通成员',
        email: null,
        status: 'ACTIVE',
        revision: 1,
        must_change_password: false,
        data_scope: 'SELF',
        role_ids: [3],
        permission_codes: ['rd.feedback.view'],
      })
    }
    if (pathname === '/api/v1/notifications' && method === 'GET') {
      return json([{
        id: 42,
        type: 'FEEDBACK',
        title: '反馈 FB-001 已上线',
        content: '已随版本发布。',
        entity_type: 'FEEDBACK',
        entity_id: 123,
        read_at: null,
        created_at: '2026-09-24T00:00:00Z',
      }])
    }
    if (pathname === '/api/v1/notifications/42/read' && method === 'POST') {
      readRequests.push(42)
      return json({ ok: true })
    }
    if (pathname === '/api/v1/feedbacks/123' && method === 'GET') {
      return json({
        id: 123,
        feedback_no: 'FB-001',
        title: '发布验收反馈',
        feedback_type: 'OTHER',
        urgency: 'NORMAL',
        status: 'ONLINE',
        system_id: null,
        module_id: null,
        submitter_id: 7,
        description: '发布验收',
        expected_result: null,
        actual_result: null,
        reproduce_steps: null,
        main_requirement_id: 12,
        duplicate_of_id: null,
        created_at: '2026-09-24T00:00:00Z',
        updated_at: '2026-09-24T00:00:00Z',
        updated_by: 7,
        revision: 1,
      })
    }
    if (['/api/v1/feedbacks/123/attachments', '/api/v1/feedbacks/123/comments'].includes(pathname) && method === 'GET') {
      return json([])
    }
    throw new Error(`Unexpected API request: ${method} ${pathname}`)
  })

  await page.goto('/#/notifications')
  await expect(page.getByText('反馈 FB-001 已上线')).toBeVisible()
  await page.getByRole('button', { name: /反馈 FB-001 已上线/ }).click()

  await expect.poll(() => readRequests.length).toBe(1)
  expect(pageErrors).toEqual([])
  await expect(page).toHaveURL(/\/#\/feedbacks\/123$/)
  await expect(page.getByRole('heading', { name: '发布验收反馈' })).toBeVisible()
  expect(readRequests).toEqual([42])
  expect(pageErrors).toEqual([])
})
