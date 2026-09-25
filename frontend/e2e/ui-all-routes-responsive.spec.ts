import { expect, test } from '@playwright/test'

const date = '2026-09-24T00:00:00Z'
const longTitle = '跨团队协作需求标题用于验证移动端换行和长文本展示 ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'
const admin = {
  id: 1, username: 'administrator-with-a-long-username', display_name: '系统管理员',
  email: 'administrator-with-a-long-address@example.com', status: 'ACTIVE', revision: 1,
  must_change_password: false, data_scope: 'ALL', role_ids: [2], permission_codes: ['*'],
}
const feedback = {
  id: 1, feedback_no: 'FB-2026-00001', title: longTitle, feedback_type: 'FEATURE',
  urgency: 'NORMAL', status: 'ACCEPTED', system_id: null, module_id: null, submitter_id: 1,
  description: longTitle.repeat(2), expected_result: '希望协作流程清晰', actual_result: null,
  reproduce_steps: null, main_requirement_id: null, duplicate_of_id: null,
  created_at: date, updated_at: date, updated_by: 1, revision: 2,
}
const requirement = {
  id: 2, requirement_no: 'REQ-2026-00002', title: longTitle, requirement_type: 'FEATURE',
  source: 'DIRECT', priority: 'P2', status: 'DONE', system_id: null, module_id: null,
  owner_id: 1, current_version_id: 3, description: longTitle.repeat(2),
  acceptance_criteria: '协作主链路可完整使用', created_at: date, updated_at: date,
  updated_by: 1, revision: 3,
}
const version = {
  id: 3, version_no: 'V1.5.0', name: longTitle, status: 'READY', owner_id: 1,
  planned_release_date: '2026-10-01', released_at: null, description: longTitle.repeat(2),
  created_at: date, updated_at: date, updated_by: 1, revision: 4,
}
const release = {
  id: 4, version_id: 3, released_at: date, result: 'SUCCESS', release_notes: longTitle,
  rollback_notes: null, created_at: date, created_by: 1, revision: 1,
}
const audit = {
  id: 9, entity_type: 'REQUIREMENT', entity_id: 2, action: 'STATUS_CHANGE',
  operator: { id: 1, username: admin.username, display_name: admin.display_name },
  before: { status: 'TESTING' }, after: { status: 'DONE' }, created_at: date,
}
const role = {
  id: 2, code: 'PROJECT_ADMIN', name: '项目管理员', data_scope: 'ALL',
  enabled: true, is_system: false, revision: 4, permission_ids: [11],
}
const permission = {
  id: 11, code: 'sys.user.view', name: '查看用户', category: 'User', group: '用户管理',
  sensitive: false, deprecated: false, replacement_code: null,
}

function pageOf(item: unknown) {
  return { items: [item], page: 1, page_size: 20, size: 20, total: 1 }
}

const responses: Record<string, unknown> = {
  '/api/v1/auth/me': admin,
  '/api/v1/dashboard/overview': {
    data_scope: 'ALL', feedback: { pending_count: 1, total_count: 1, by_status: { ACCEPTED: 1 } },
    requirements: { active_count: 0, total_count: 1, by_status: { DONE: 1 } },
    versions: { active_count: 1, total_count: 1, by_status: { READY: 1 },
      recent_active_versions: [{ id: 3, version_no: version.version_no, name: version.name,
        status: 'READY', planned_release_date: version.planned_release_date, updated_at: date }] },
    releases: { total_count: 1, recent_releases: [{ id: 4, version_id: 3,
      version_no: version.version_no, version_name: version.name, released_at: date, result: 'SUCCESS' }] },
  },
  '/api/v1/systems': { systems: [], modules: [] },
  '/api/v1/feedbacks': pageOf(feedback),
  '/api/v1/feedbacks/1': feedback,
  '/api/v1/feedbacks/1/attachments': [],
  '/api/v1/feedbacks/1/comments': [],
  '/api/v1/requirements': pageOf(requirement),
  '/api/v1/requirements/2': requirement,
  '/api/v1/requirements/2/feedbacks': [],
  '/api/v1/versions': pageOf(version),
  '/api/v1/versions/3': version,
  '/api/v1/versions/3/requirements': {
    version_id: 3, stats: { total: 1, by_status: { DONE: 1 }, completed: 1, completion_rate: 1 },
    items: [requirement],
  },
  '/api/v1/releases': pageOf(release),
  '/api/v1/notifications': [{ id: 8, type: 'SYSTEM', title: '系统通知', content: longTitle,
    entity_type: null, entity_id: null, read_at: null, created_at: date }],
  '/api/v1/audits': pageOf(audit),
  '/api/v1/users': pageOf({ id: 1, username: admin.username, display_name: admin.display_name,
    email: admin.email, mobile: null, status: 'ACTIVE', revision: 1, role_ids: [2] }),
  '/api/v1/roles': [role],
  '/api/v1/roles/permissions': [permission],
}

test('guest login fits every release viewport', async ({ page }) => {
  for (const width of [375, 390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/login')
    await expect(page.getByRole('button', { name: '登录' })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth), `${width}px login`).toBeLessThanOrEqual(width + 1)
  }
})

test('all 18 authenticated screens render at every release viewport', async ({ page }) => {
  test.setTimeout(180000)
  const pageErrors: string[] = []
  const unexpectedRequests: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'responsive-test-access')
    localStorage.setItem('iterflow.refresh_token', 'responsive-test-refresh')
  })
  await page.route('**/api/v1/**', (route) => {
    const { pathname } = new URL(route.request().url())
    if (pathname.startsWith('/api/v1/editing/')) return route.fulfill({ status: 200, json: {} })
    if (!(pathname in responses)) {
      unexpectedRequests.push(`${route.request().method()} ${pathname}`)
      return route.fulfill({ status: 500, json: { detail: 'unmocked request' } })
    }
    return route.fulfill({ status: 200, json: responses[pathname] })
  })

  const paths: [string, string][] = [
    ['/', '待处理反馈'], ['/feedbacks', feedback.feedback_no], ['/feedbacks/new', '提交反馈'],
    ['/feedbacks/1', longTitle], ['/requirements', requirement.requirement_no],
    ['/requirements/new', '新建需求'], ['/requirements/2', longTitle],
    ['/versions', version.version_no], ['/versions/new', '新建版本'],
    ['/versions/3', longTitle], ['/releases', release.release_notes],
    ['/notifications', '系统通知'], ['/profile', admin.email],
    ['/admin/audits', audit.action], ['/system/users', admin.username],
    ['/admin/roles', role.name], ['/change-password?from=profile', '修改密码'],
    ['/forbidden', '无权访问'],
  ]
  for (const width of [375, 390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    for (const [path, expected] of paths) {
      await page.goto(path)
      await expect(page.locator('h1').first(), `${path} at ${width}px`).toBeVisible()
      await expect(page.getByText(expected, { exact: true }).first(), `${path} data at ${width}px`).toBeVisible()
      await expect(page).toHaveURL(new RegExp(path.split('?')[0].replaceAll('/', '\\/') + '(?:\\?|$)'))
      const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
      expect(scrollWidth, `${path} at ${width}px`).toBeLessThanOrEqual(width + 1)
    }
  }
  expect(unexpectedRequests).toEqual([])
  expect(pageErrors).toEqual([])
})

test('core detail dialogs stay operable on a 375px screen', async ({ page }) => {
  const unexpectedRequests: string[] = []
  await page.setViewportSize({ width: 375, height: 900 })
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'responsive-test-access')
    localStorage.setItem('iterflow.refresh_token', 'responsive-test-refresh')
  })
  await page.route('**/api/v1/**', (route) => {
    const { pathname } = new URL(route.request().url())
    if (pathname.startsWith('/api/v1/editing/')) return route.fulfill({ status: 200, json: {} })
    if (pathname === '/api/v1/versions/3/publish/check') {
      return route.fulfill({ status: 200, json: { passed: true, checks: [] } })
    }
    if (!(pathname in responses)) {
      unexpectedRequests.push(`${route.request().method()} ${pathname}`)
      return route.fulfill({ status: 500, json: { detail: 'unmocked request' } })
    }
    return route.fulfill({ status: 200, json: responses[pathname] })
  })

  async function checkDialog() {
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    const bounds = await dialog.boundingBox()
    expect(bounds).not.toBeNull()
    expect(bounds!.x).toBeGreaterThanOrEqual(-1)
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(376)
    const footer = await dialog.locator('.el-dialog__footer').boundingBox()
    if (footer) expect(footer.y + footer.height).toBeLessThanOrEqual(901)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(376)
  }

  await page.goto('/feedbacks/1')
  await expect(page.getByRole('heading', { name: longTitle })).toBeVisible()
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  await checkDialog()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '转需求' }).click()
  await checkDialog()
  await page.goto('/requirements/2')
  await expect(page.getByRole('heading', { name: longTitle })).toBeVisible()
  await page.getByRole('button', { name: '重新开发' }).click()
  await checkDialog()
  await page.goto('/versions/3')
  await expect(page.getByRole('heading', { name: longTitle })).toBeVisible()
  await page.getByRole('button', { name: '发布', exact: true }).click()
  await checkDialog()
  expect(unexpectedRequests).toEqual([])
})
