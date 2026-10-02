import { expect, test } from '@playwright/test'

const date = '2026-09-29T00:00:00Z'
const longName = `测试用户B${'很长的姓名'.repeat(24)}`
const user = {
  id: 1, username: 'editor', display_name: '编辑者', email: null, status: 'ACTIVE',
  revision: 1, must_change_password: false, data_scope: 'ALL', role_ids: [1],
  permission_codes: [
    'rd.feedback.view', 'rd.feedback.edit', 'rd.requirement.view', 'rd.requirement.edit',
    'rd.version.view', 'rd.version.edit',
  ],
}
const data: Record<string, unknown> = {
  '/api/v1/auth/me': user,
  '/api/v1/feedbacks/1': {
    id: 1, feedback_no: 'FB-1', title: '反馈标题', feedback_type: 'OTHER', urgency: 'NORMAL',
    status: 'NEW', system_id: null, module_id: null, submitter_id: 1,
    description: '反馈描述', expected_result: null, actual_result: null, reproduce_steps: null,
    main_requirement_id: null, duplicate_of_id: null, created_at: date, updated_at: date,
    updated_by: 1, revision: 1,
  },
  '/api/v1/feedbacks/1/attachments': [],
  '/api/v1/feedbacks/1/comments': [],
  '/api/v1/requirements/2': {
    id: 2, requirement_no: 'REQ-2', title: '需求标题', requirement_type: 'FEATURE',
    source: 'DIRECT', priority: 'P2', status: 'DRAFT', system_id: null, module_id: null,
    owner_id: null, current_version_id: null, description: '需求描述', acceptance_criteria: null,
    created_at: date, updated_at: date, updated_by: 1, revision: 1,
  },
  '/api/v1/requirements/2/feedbacks': [],
  '/api/v1/versions/3': {
    id: 3, version_no: 'V-3', name: '版本标题', status: 'PLANNING', owner_id: null,
    planned_release_date: null, released_at: null, description: null,
    created_at: date, updated_at: date, updated_by: 1, revision: 1,
  },
  '/api/v1/versions/3/requirements': {
    version_id: 3, stats: { total: 0, by_status: {}, completed: 0, completion_rate: 0 }, items: [],
  },
}

for (const width of [375, 390, 768, 1280, 1440]) {
  test(`editing presence follows field-edit dialogs at ${width}px`, async ({ context }) => {
    test.setTimeout(90_000)
    await context.addInitScript(() => {
      localStorage.setItem('iterflow.access_token', 'presence-test-access')
      localStorage.setItem('iterflow.refresh_token', 'presence-test-refresh')
    })
    for (const [path, entity, id, title] of [
      ['/feedbacks/1', 'FEEDBACK', 1, '反馈标题'],
      ['/requirements/2', 'REQUIREMENT', 2, '需求标题'],
      ['/versions/3', 'VERSION', 3, '版本标题'],
    ] as const) {
      const page = await context.newPage()
      const calls: { operation: string; entity_type: string; entity_id: number }[] = []
      const unexpected: string[] = []
      await page.setViewportSize({ width, height: 900 })
      await page.route('**/api/v1/**', (route) => {
        const { pathname } = new URL(route.request().url())
        if (pathname === '/api/v1/notifications/unread-count') return route.fulfill({ status: 200, json: { unread_count: 0 } })
        if (pathname.startsWith('/api/v1/editing/')) {
          const operation = pathname.split('/').at(-1)!
          const body = route.request().postDataJSON() as { entity_type: string; entity_id: number }
          calls.push({ operation, ...body })
          return route.fulfill({ status: 200, json: operation === 'start'
            ? { existing_editor: { user_id: 2, display_name: longName, active_at: date } }
            : operation === 'heartbeat'
              ? { ok: false, existing_editor: { user_id: 2, display_name: longName, active_at: date } }
              : { ok: true } })
        }
        if (pathname in data) return route.fulfill({ status: 200, json: data[pathname] })
        unexpected.push(`${route.request().method()} ${pathname}`)
        return route.fulfill({ status: 500, json: {} })
      })
      await page.goto(`/#${path}`)
      await expect(page.getByRole('heading', { name: title })).toBeVisible()
      await expect(page.getByRole('button', { name: '编辑', exact: true })).toBeVisible()
      expect(calls, `${path} must not start on detail mount`).toEqual([])
      await page.getByRole('button', { name: '编辑', exact: true }).click()
      const dialog = page.getByRole('dialog')
      await expect(dialog).toBeVisible()
      await expect(dialog.getByText(longName, { exact: false })).toBeVisible()
      await expect(dialog.getByRole('button', { name: '保存' })).toBeEnabled()
      await expect.poll(() => calls.filter((call) => call.operation === 'start').length).toBe(1)
      expect(calls[0]).toEqual({ operation: 'start', entity_type: entity, entity_id: id })
      expect(await page.evaluate(() => document.documentElement.scrollWidth), `${path} at ${width}px`).toBeLessThanOrEqual(width + 1)
      await page.keyboard.press('Escape')
      await expect(dialog).toHaveCount(0)
      await expect.poll(() => calls.filter((call) => call.operation === 'end').length).toBe(1)
      expect(unexpected).toEqual([])
      await page.close()
    }
  })
}
