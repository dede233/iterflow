import { mockCollaboration } from './collaboration-fixture'
import { expect, test } from '@playwright/test'

const date = '2026-09-24T00:00:00Z'
const longTitle = '跨团队协作需求标题用于验证移动端换行和长文本展示 ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'
const longUsername = 'u'.repeat(64)
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
    activities: [],
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
      '/api/v1/requirements/2/collaborators': { revision: 1, owner: null, developers: [], designers: [], development_completions: [] },
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
  '/api/v1/users': pageOf({ id: 5, username: longUsername, display_name: '系统协作者',
    email: admin.email, mobile: null, status: 'ACTIVE', revision: 1, role_ids: [2] }),
  '/api/v1/roles': [role],
  '/api/v1/roles/permissions': [permission],
  '/api/v1/systems/manage': { systems: [], modules: [] },
}

test('guest login fits every release viewport', async ({ page }) => {
  for (const width of [375, 390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/login')
    await expect(page.getByRole('button', { name: '登录' })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth), `${width}px login`).toBeLessThanOrEqual(width + 1)
  }
})

test('all 19 authenticated screens render at every release viewport', async ({ page }, info) => {
  test.setTimeout(180000)
  const pageErrors: string[] = []
  const unexpectedRequests: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'responsive-test-access')
    localStorage.setItem('iterflow.refresh_token', 'responsive-test-refresh')
  })
  await page.route('**/api/v1/**', async (route) => {
    if (await mockCollaboration(route)) return
    const { pathname } = new URL(route.request().url())
    if (pathname === '/api/v1/notifications/unread-count') return route.fulfill({ status: 200, json: { unread_count: 0 } })
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
    ['/admin/audits', '变更状态'], ['/admin/systems', '暂无系统，先创建一个业务系统'], ['/system/users', longUsername],
    ['/admin/roles', role.name], ['/change-password?from=profile', '修改密码'],
    ['/forbidden', '无权访问'],
  ]
  for (const width of [375, 390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    for (const [path, expected] of paths) {
      await page.goto(`/#${path}`)
      await expect(page.locator('h1').first(), `${path} at ${width}px`).toBeVisible()
      await expect(page.getByText(expected, { exact: true }).first(), `${path} data at ${width}px`).toBeVisible()
      await expect(page).toHaveURL(new RegExp(`#${path.split('?')[0].replaceAll('/', '\\/')}(?:\\?|$)`))
      const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
      expect(scrollWidth, `${path} at ${width}px`).toBeLessThanOrEqual(width + 1)
      // Visibility/overflow alone missed unequal buttons and vertically shifted actions.
      const actionLayoutProblems = await page.evaluate(() => {
        const problems: string[] = []
        for (const group of document.querySelectorAll('.page-header__actions, .section-card__actions, .editor-actions, .form-actions, .filter-actions')) {
          const bounds = group.getBoundingClientRect()
          if (!bounds.width || !bounds.height) continue
          const controls = [...group.children].filter(e => e.matches('button, a, .unread-count')).map(e => ({ text: e.textContent?.trim(), r: e.getBoundingClientRect() })).filter(e => e.r.width && e.r.height)
          for (const { text, r } of controls) if (r.left < bounds.left - 1 || r.right > bounds.right + 1) problems.push(`${text}: exceeds action group`)
          for (let i = 0; i < controls.length; i++) for (let j = i + 1; j < controls.length; j++) {
            const a = controls[i]!, b = controls[j]!
            const sameRow = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top) > 1
            if (sameRow && Math.abs(a.r.top + a.r.height / 2 - b.r.top - b.r.height / 2) > 1) problems.push(`${a.text}/${b.text}: center misalignment`)
            if (sameRow && Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left) > 1) problems.push(`${a.text}/${b.text}: overlapping controls`)
          }
        }
        return problems
      })
      expect(actionLayoutProblems, `${path} actions at ${width}px`).toEqual([])
      if (width === 1280 && path === '/feedbacks') {
        const sidebar = page.locator('.side-nav')
        await expect(sidebar.getByRole('link', { name: '首页' })).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
        await expect(sidebar.getByRole('link', { name: '反馈中心' })).not.toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
      }
      if (path === '/system/users' && (width === 375 || width === 1440)) {
        const account = page.locator(width === 375 ? '.user-card' : '.el-table__row').filter({ hasText: longUsername })
        const status = account.locator('.status-tag')
        await expect(status).toHaveText('启用')
        await expect(status).toBeInViewport({ ratio: 1 })
        const textFits = await account.evaluate((element, username) => {
          const bounds = element.getBoundingClientRect()
          const id = [...element.querySelectorAll('.user-card__id, .cell')].find(cell => cell.textContent === username)!
          const idBounds = id.getBoundingClientRect()
          const badge = element.querySelector('.status-tag')!.getBoundingClientRect()
          const range = document.createRange()
          range.selectNodeContents(id)
          const lines = [...range.getClientRects()]
          const badgeFits = badge.left >= bounds.left && badge.right <= bounds.right
          const usernameFits = lines.length > 0 && lines.every(line =>
            line.left >= Math.max(bounds.left, idBounds.left) - 1 &&
            line.right <= Math.min(bounds.right, idBounds.right, badge.left) + 1,
          )
          return badgeFits && usernameFits
        }, longUsername)
        expect(textFits, `username and status fit within the account at ${width}px`).toBe(true)
        await page.screenshot({ path: info.outputPath(`long-username-${width}.png`) })
      }
    }
  }
  expect(unexpectedRequests).toEqual([])
  expect(pageErrors).toEqual([])
})

test('core detail dialogs stay operable on a 375px screen', async ({ page }, info) => {
  const unexpectedRequests: string[] = []
  const viewport = { width: 375, height: 812 }
  await page.setViewportSize(viewport)
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'responsive-test-access')
    localStorage.setItem('iterflow.refresh_token', 'responsive-test-refresh')
  })
  await page.route('**/api/v1/**', async (route) => {
    if (await mockCollaboration(route)) return
    const { pathname } = new URL(route.request().url())
    const method = route.request().method()
    if (pathname === '/api/v1/notifications/unread-count') return route.fulfill({ status: 200, json: { unread_count: 0 } })
    if (pathname.startsWith('/api/v1/editing/')) return route.fulfill({ status: 200, json: {} })
    if (method === 'POST' && pathname === '/api/v1/versions/3/publish/check') {
      return route.fulfill({ status: 200, json: { passed: true, checks: [] } })
    }
    if (method !== 'GET' || !(pathname in responses)) {
      unexpectedRequests.push(`${method} ${pathname}`)
      return route.fulfill({ status: 500, json: { detail: 'unmocked request' } })
    }
    return route.fulfill({ status: 200, json: responses[pathname] })
  })

  async function checkDialog(name: string, submitLabel: string, footerSelector = '.el-dialog__footer') {
    const dialog = page.getByRole('dialog', { name, exact: true })
    await expect(dialog).toBeVisible()
    const footer = dialog.locator(footerSelector)
    const cancel = footer.getByRole('button', { name: '取消', exact: true })
    for (const button of [cancel, footer.getByRole('button', { name: submitLabel, exact: true })]) {
      await expect(button).toBeInViewport({ ratio: 1 })
      await button.click({ trial: true })
    }
    const bounds = (await dialog.boundingBox())!
    const footerBounds = (await footer.boundingBox())!
    expect(bounds.x).toBeGreaterThanOrEqual(-1)
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(viewport.width + 1)
    expect(bounds.y).toBeGreaterThanOrEqual(-1)
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(viewport.height + 1)
    expect(footerBounds.y + footerBounds.height).toBeLessThanOrEqual(bounds.y + bounds.height + 1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width + 1)
    return { dialog, footer, cancel }
  }

  await page.goto('/#/feedbacks/1')
  await expect(page.getByRole('heading', { name: longTitle })).toBeVisible()
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  const edit = await checkDialog('编辑反馈', '保存')
  await page.keyboard.press('Escape')
  await expect(edit.dialog).toBeHidden()

  await page.getByRole('button', { name: '新建需求', exact: true }).click()
  const create = await checkDialog('新建需求', '创建', '.editor-actions')
  const fields = create.dialog.locator('.create-form-fields')
  await expect(fields.getByRole('textbox', { name: /标题/ })).toHaveValue(feedback.title)
  await fields.getByText('后续人员安排', { exact: false }).click()
  await expect(fields.locator('.optional-people')).toHaveAttribute('open', '')
  await fields.evaluate(element => { element.scrollTop = 0 })
  const footerTop = (await create.footer.boundingBox())!.y
  const scroll = await fields.evaluate(element => {
    element.scrollTop = element.scrollHeight
    const body = element.closest('.el-dialog__body')!
    return {
      top: element.scrollTop,
      remaining: element.scrollHeight - element.clientHeight - element.scrollTop,
      bottom: element.getBoundingClientRect().bottom,
      bodyOverflow: body.scrollHeight - body.clientHeight,
    }
  })
  expect(scroll.top).toBeGreaterThan(0)
  expect(scroll.remaining).toBeLessThanOrEqual(1)
  expect(scroll.bottom).toBeLessThanOrEqual(footerTop + 1)
  expect(scroll.bodyOverflow).toBeLessThanOrEqual(1)
  await checkDialog('新建需求', '创建', '.editor-actions')
  expect(Math.abs((await create.footer.boundingBox())!.y - footerTop)).toBeLessThanOrEqual(1)
  await page.screenshot({ path: info.outputPath('feedback-to-requirement-375.png') })
  await create.cancel.click()
  const close = page.getByRole('dialog', { name: '确认关闭？', exact: true })
  await expect(create.dialog).toBeVisible()
  await close.getByRole('button', { name: '关闭表单', exact: true }).click()
  await expect(create.dialog).toBeHidden()

  await page.goto('/#/requirements/2')
  await expect(page.getByRole('heading', { name: longTitle })).toBeVisible()
  await page.getByRole('button', { name: '展开需求进度', exact: true }).click()
  await page.getByRole('button', { name: '重新开发', exact: true }).click()
  const redevelop = await checkDialog('重新开发', '确定')
  await redevelop.dialog.getByRole('textbox').fill('移动端核对重新开发原因')
  await redevelop.cancel.click()
  await expect(redevelop.dialog).toBeHidden()

  await page.goto('/#/versions/3')
  await expect(page.getByRole('heading', { name: longTitle })).toBeVisible()
  await page.getByRole('button', { name: '发布版本', exact: true }).click()
  const publish = await checkDialog('发布版本', '确认发布')
  await publish.dialog.getByRole('textbox', { name: '发布说明', exact: true }).fill('移动端核对发布说明')
  await publish.cancel.click()
  await expect(publish.dialog).toBeHidden()
  expect(unexpectedRequests).toEqual([])
})
