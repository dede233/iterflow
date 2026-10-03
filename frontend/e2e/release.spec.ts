import { randomUUID } from 'node:crypto'
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

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

  await page.goto('/#/')
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

  await page.goto('/#/feedbacks')
  await expect(page.getByRole('heading', { name: '反馈中心' })).toBeVisible()
  await page.goto('/#/feedbacks/new')
  const title = `发布验收反馈-${Date.now()}`
  await page.locator('.el-form-item').filter({ hasText: '标题' }).locator('input').fill(title)
  await page.locator('.el-form-item').filter({ hasText: '详细描述' }).locator('textarea').fill('生产构建浏览器验收反馈')
  await page.getByRole('button', { name: '提交', exact: true }).click()
  await expect(page).toHaveURL(/\/#\/feedbacks\/\d+$/)
  await page.goto('/#/feedbacks')
  await expect(page.getByText(title)).toBeVisible()
  expect(browserErrors).toEqual([])
})

async function api(request: APIRequestContext, token: string, method: string, path: string, data?: unknown) {
  const response = await request.fetch(`/api/v1${path}`, {
    method, data, headers: { Authorization: `Bearer ${token}` },
  })
  expect(response.ok(), `${method} ${path}`).toBeTruthy()
  return response.json()
}

async function login(page: Page, username: string, password: string) {
  await page.goto('/#/login')
  await page.getByPlaceholder('用户名').fill(username)
  await page.getByPlaceholder('密码').fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('heading', { name: '首页 / 系统概览' })).toBeVisible()
}

async function status(page: Page, label: string, path: string) {
  await page.getByRole('button', { name: label, exact: true }).click()
  const dialog = page.getByRole('dialog', { name: label, exact: true })
  const response = page.waitForResponse(r => r.url().endsWith(`/api/v1${path}/status`) && r.request().method() === 'PATCH')
  await dialog.getByRole('button', { name: '确定', exact: true }).click()
  expect((await response).status()).toBe(200)
  await expect(dialog).toHaveCount(0)
}

test('Phase 7 real restricted users: presence, conflict, publish, notification and all viewports', async ({ browser, request }) => {
  test.setTimeout(300_000)
  // This file runs sequentially: the existing first test changes the disposable admin password.
  const adminName = process.env.INIT_ADMIN_USERNAME!
  const adminPassword = process.env.ITERFLOW_BROWSER_NEW_PASSWORD!
  const adminLogin = await request.post('/api/v1/auth/login', { data: { username: adminName, password: adminPassword } })
  expect(adminLogin.status()).toBe(200)
  const adminToken = (await adminLogin.json()).access_token as string
  const permissions: { id: number; code: string; deprecated: boolean }[] = await api(request, adminToken, 'GET', '/roles/permissions')
  const suffix = randomUUID().slice(0, 8)
  async function user(name: string, scope: 'SELF' | 'ALL', codes: string[]) {
    const role = await api(request, adminToken, 'POST', '/roles', {
      code: `P7_${name}_${suffix}`, name: `P7 ${name}`, data_scope: scope,
      permission_ids: permissions.filter(p => codes.includes(p.code)).map(p => p.id),
    })
    const password = randomUUID()
    const username = `p7-${name}-${suffix}`
    const created = await api(request, adminToken, 'POST', '/users', { username, display_name: `P7 ${name}`, password, role_ids: [role.id] })
    const pair = await request.post('/api/v1/auth/login', { data: { username, password } })
    expect(pair.status()).toBe(200)
    const changed = await api(request, (await pair.json()).access_token, 'POST', '/auth/change-password', {
      current_password: password, new_password: `${password}-changed`,
    })
    return { id: created.id as number, username, password: `${password}-changed`, token: changed.access_token as string }
  }
  const submitter = await user('submitter', 'SELF', ['dashboard.view', 'rd.feedback.view', 'rd.feedback.create'])
  const managerCodes = permissions.filter(p => p.code.startsWith('rd.') && !p.deprecated).map(p => p.code)
  managerCodes.push('dashboard.view', 'sys.audit.view', 'sys.user.view', 'sys.system.view')
  const a = await user('A', 'ALL', managerCodes)
  const b = await user('B', 'ALL', managerCodes)
  const contexts = await Promise.all([browser.newContext(), browser.newContext(), browser.newContext(), browser.newContext()])
  const pages = await Promise.all(contexts.map(context => context.newPage()))
  const [submit, pageA, pageB, admin] = pages
  const errors: string[] = []
  pages.forEach(page => { page.setDefaultTimeout(15_000); page.on('pageerror', error => errors.push(error.message)) })
  try {
    await login(submit, submitter.username, submitter.password)
    await login(pageA, a.username, a.password)
    await login(pageB, b.username, b.password)
    await login(admin, adminName, adminPassword)
    const title = `Phase 7 browser chain ${suffix}`
    await submit.goto('/#/feedbacks/new')
    await submit.locator('.el-form-item').filter({ hasText: '标题' }).locator('input').fill(title)
    await submit.locator('.el-form-item').filter({ hasText: '详细描述' }).locator('textarea').fill('Real isolated PostgreSQL browser acceptance')
    const created = submit.waitForResponse(r => r.url().endsWith('/api/v1/feedbacks') && r.request().method() === 'POST')
    await submit.getByRole('button', { name: '提交', exact: true }).click()
    const feedback = await (await created).json()
    await expect(submit).toHaveURL(new RegExp(`#/feedbacks/${feedback.id}$`))
    await pageA.goto(`/#/feedbacks/${feedback.id}`)
    await status(pageA, '受理', `/feedbacks/${feedback.id}`)
    await pageA.getByRole('button', { name: '转需求', exact: true }).click()
    const converted = pageA.waitForResponse(r => r.url().endsWith(`/feedbacks/${feedback.id}/convert`) && r.request().method() === 'POST')
    // Finish the conversion navigation's first detail read before assignment/reload.
    // URL changes alone do not mean that the detail response body is available.
    const initialDetail = pageA.waitForResponse(r => /\/api\/v1\/requirements\/\d+$/.test(r.url()) && r.request().method() === 'GET').then(r => r.json())
    await pageA.getByRole('dialog', { name: '转为需求' }).getByRole('button', { name: '确定', exact: true }).click()
    const requirement = await (await converted).json()
    await expect(pageA).toHaveURL(new RegExp(`#/requirements/${requirement.id}\\?return_to=%2Ffeedbacks$`))
    const initialRequirement = await initialDetail
    expect(initialRequirement.id).toBe(requirement.id)
    expect(initialRequirement.revision).toBe(requirement.revision)
    // Assignment is API setup; the subsequent title/priority editing and statuses are real UI.
    const assigned = await api(request, a.token, 'PATCH', `/requirements/${requirement.id}`, { owner_id: a.id, priority: 'P1', revision: requirement.revision })
    // A same-hash navigation does not remount the detail view. Reload after API setup
    // and verify both editors have actually fetched the assigned revision.
    const loadedA = pageA.waitForResponse(r => r.url().endsWith(`/requirements/${requirement.id}`) && r.request().method() === 'GET').then(r => r.json())
    await pageA.reload()
    expect((await loadedA).revision).toBe(assigned.revision)
    const loadedB = pageB.waitForResponse(r => r.url().endsWith(`/requirements/${requirement.id}`) && r.request().method() === 'GET').then(r => r.json())
    await pageB.goto(`/#/requirements/${requirement.id}`)
    expect((await loadedB).revision).toBe(assigned.revision)
    const presence: { actor: string; operation: string }[] = []
    for (const [actor, page] of [['A', pageA], ['B', pageB]] as const) {
      page.on('request', r => {
        if (r.url().includes('/api/v1/editing/') && r.postDataJSON()?.entity_id === requirement.id) {
          presence.push({ actor, operation: r.url().split('/').at(-1)! })
        }
      })
    }
    expect(presence).toEqual([])
    await pageA.clock.install()
    const startA = pageA.waitForResponse(r => r.url().endsWith('/editing/start'))
    await pageA.getByRole('button', { name: '编辑', exact: true }).click()
    expect((await startA).status()).toBe(200)
    await expect.poll(() => presence.filter(p => p.actor === 'A' && p.operation === 'start').length).toBe(1)
    await expect(pageA.getByRole('dialog', { name: '编辑需求' }).getByRole('button', { name: '保存' })).toBeEnabled()
    const beat = pageA.waitForResponse(r => r.url().endsWith('/editing/heartbeat'))
    // Advance only browser timers; the heartbeat itself reaches real Redis through the real API.
    await pageA.clock.fastForward(120_000)
    expect((await beat).status()).toBe(200)
    await pageB.getByRole('button', { name: '编辑', exact: true }).click()
    const editB = pageB.getByRole('dialog', { name: '编辑需求' })
    await expect(editB.getByText('P7 A 正在编辑此需求')).toBeVisible()
    await expect(editB.getByRole('button', { name: '保存' })).toBeEnabled()
    const titleInput = (page: Page) => page.getByRole('dialog', { name: '编辑需求' }).locator('.el-form-item').filter({ hasText: '标题' }).locator('input')
    await titleInput(pageA).fill(`${title} saved A`)
    await titleInput(pageB).fill(`${title} local B`)
    const saveA = pageA.waitForResponse(r => r.url().endsWith(`/requirements/${requirement.id}`) && r.request().method() === 'PATCH')
    await pageA.getByRole('dialog', { name: '编辑需求' }).getByRole('button', { name: '保存' }).click()
    expect((await saveA).status()).toBe(200)
    await expect.poll(() => presence.filter(p => p.actor === 'A' && p.operation === 'end').length).toBe(1)
    await pageA.clock.resume()
    const conflict = pageB.getByRole('dialog', { name: '数据已被其他用户修改' })
    async function staleSave() {
      const response = pageB.waitForResponse(r => r.url().endsWith(`/requirements/${requirement.id}`) && r.request().method() === 'PATCH')
      await editB.getByRole('button', { name: '保存' }).click()
      const failed = await response
      expect(failed.status()).toBe(409)
      const body = await failed.json()
      expect(body.code).toBe(40910)
      expect(body.data.current_revision).toBe(assigned.revision + 1)
      await expect(conflict).toBeVisible()
      await expect(titleInput(pageB)).toHaveValue(`${title} local B`)
      await expect(pageB.getByText('服务器版本已变化，请查看冲突详情')).toHaveCount(0)
      expect(presence.filter(p => p.actor === 'B' && p.operation === 'end')).toHaveLength(0)
    }
    await staleSave()
    await conflict.getByRole('button', { name: '关闭并人工处理' }).click()
    await expect(titleInput(pageB)).toHaveValue(`${title} local B`)
    await staleSave()
    const reload = pageB.waitForResponse(r => r.url().endsWith(`/requirements/${requirement.id}`) && r.request().method() === 'GET')
    await conflict.getByRole('button', { name: '重新加载服务器版本' }).click()
    expect((await reload).status()).toBe(200)
    await expect(conflict).toHaveCount(0)
    await expect(titleInput(pageB)).toHaveValue(`${title} saved A`)
    await titleInput(pageB).fill(`${title} reviewed B`)
    const savedB = pageB.waitForResponse(r => r.url().endsWith(`/requirements/${requirement.id}`) && r.request().method() === 'PATCH')
    await editB.getByRole('button', { name: '保存' }).click()
    const saveResponseB = await savedB
    expect(saveResponseB.status()).toBe(200)
    const saveRequest = saveResponseB.request().postDataJSON()
    expect(saveRequest.revision).toBe(assigned.revision + 1)
    await expect(editB).toHaveCount(0)
    await expect.poll(() => presence.filter(p => p.actor === 'B' && p.operation === 'end').length).toBe(1)
    const version = await api(request, a.token, 'POST', '/versions', { version_no: `P7-${suffix}`, name: title, owner_id: a.id })
    await pageA.goto(`/#/versions/${version.id}`)
    await pageA.getByRole('button', { name: '添加需求', exact: true }).click()
    await pageA.getByRole('dialog', { name: '添加需求' }).getByRole('button', { name: '选择需求' }).click()
    const selector = pageA.getByRole('dialog', { name: '选择需求', exact: true })
    await selector.getByRole('textbox', { name: '搜索需求' }).fill(title)
    await selector.locator('.selector-option').filter({ hasText: requirement.requirement_no }).click()
    await expect(selector).not.toBeVisible()
    const relation = pageA.waitForResponse(r => r.url().endsWith(`/versions/${version.id}/requirements`) && r.request().method() === 'POST')
    await pageA.getByRole('dialog', { name: '添加需求' }).getByRole('button', { name: '添加', exact: true }).click()
    expect((await relation).status()).toBe(200)
    await pageB.reload()
    for (const label of ['开始开发', '提测', '完成']) await status(pageB, label, `/requirements/${requirement.id}`)
    for (const label of ['开始开发', '提测', '待发布']) await status(pageA, label, `/versions/${version.id}`)
    await pageA.getByRole('button', { name: '发布', exact: true }).click()
    const publishDialog = pageA.getByRole('dialog', { name: '发布版本' })
    await expect(publishDialog.getByRole('button', { name: '确认发布' })).toBeEnabled()
    await publishDialog.locator('textarea').fill('Phase 7 real browser release')
    const current = await api(request, a.token, 'GET', `/requirements/${requirement.id}`)
    // A real concurrent business change invalidates an already displayed successful publish check.
    let reopened = await api(request, a.token, 'PATCH', `/requirements/${requirement.id}/status`, { status: 'DEVELOPING', revision: current.revision, reason: 'Phase 7 concurrent publish check' })
    const business = pageA.waitForResponse(r => r.url().endsWith(`/versions/${version.id}/publish`) && r.request().method() === 'POST')
    await publishDialog.getByRole('button', { name: '确认发布' }).click()
    const businessResponse = await business
    expect(businessResponse.status()).toBe(409)
    expect((await businessResponse.json()).code).toBe(40923)
    await expect(pageA.getByText('发布检查未通过', { exact: true })).toBeVisible()
    await expect(pageA.getByRole('dialog', { name: '数据已被其他用户修改' })).toHaveCount(0)
    await expect(publishDialog).toBeVisible()
    for (const next of ['TESTING', 'DONE']) reopened = await api(request, a.token, 'PATCH', `/requirements/${requirement.id}/status`, { status: next, revision: reopened.revision })
    await pageA.reload()
    await pageA.getByRole('button', { name: '发布', exact: true }).click()
    await publishDialog.locator('textarea').fill('Phase 7 real browser release')
    await expect(publishDialog.getByRole('button', { name: '确认发布' })).toBeEnabled()
    const published = pageA.waitForResponse(r => r.url().endsWith(`/versions/${version.id}/publish`) && r.request().method() === 'POST')
    await publishDialog.getByRole('button', { name: '确认发布' }).click()
    const result = await (await published).json()
    expect(result.release.result).toBe('SUCCESS')
    const releaseId = result.release.id as number
    await expect(publishDialog).toHaveCount(0)
    await pageA.goto(`/#/releases/${releaseId}`)
    await expect(pageA.getByText('Phase 7 real browser release', { exact: true })).toBeVisible()
    for (const label of ['编辑', '删除', '回滚']) await expect(pageA.getByRole('button', { name: label, exact: true })).toHaveCount(0)
    expect((await api(request, a.token, 'GET', `/requirements/${requirement.id}`)).status).toBe('ONLINE')
    expect((await api(request, submitter.token, 'GET', `/feedbacks/${feedback.id}`)).status).toBe('ONLINE')
    await submit.goto('/#/notifications')
    const notification = submit.locator('.notification-card').filter({ hasText: feedback.feedback_no })
    await expect(notification).toBeVisible()
    const marked = submit.waitForResponse(r => /\/notifications\/\d+\/read$/.test(r.url()))
    await notification.click()
    expect((await marked).status()).toBe(200)
    await expect(submit).toHaveURL(new RegExp(`#/feedbacks/${feedback.id}$`))
    expect((await api(request, submitter.token, 'GET', '/notifications/unread-count')).unread_count).toBe(0)
    const audits = await api(request, a.token, 'GET', `/audits?entity_type=VERSION&entity_id=${version.id}`)
    expect(audits.items.some((row: { action: string }) => row.action === 'VERSION_PUBLISH')).toBeTruthy()
    // V1.8: exercise the new selector/worklist against real SELF repositories,
    // including owner visibility, creator visibility and another account's object.
    const selfCodes = ['dashboard.view', 'rd.requirement.view', 'rd.requirement.create', 'rd.version.view', 'rd.version.edit']
    const selfA = await user('SelfA', 'SELF', selfCodes)
    const selfB = await user('SelfB', 'SELF', selfCodes)
    const prefix = `V18 scoped ${suffix}`
    const own = await api(request, adminToken, 'POST', '/requirements', { title: `${prefix} owner A`, requirement_type: 'FEATURE', priority: 'P0', description: 'Owner scope', owner_id: selfA.id })
    const createdBy = await api(request, selfA.token, 'POST', '/requirements', { title: `${prefix} creator A`, requirement_type: 'FEATURE', priority: 'P1', description: 'Creator scope' })
    const hidden = await api(request, adminToken, 'POST', '/requirements', { title: `${prefix} private B`, requirement_type: 'FEATURE', priority: 'P2', description: 'Out of scope', owner_id: selfB.id })
    let scopedVersion = await api(request, adminToken, 'POST', '/versions', { version_no: `V18-${suffix}`, name: prefix, owner_id: selfA.id })
    for (const target of [own, createdBy, hidden]) scopedVersion = await api(request, adminToken, 'POST', `/versions/${scopedVersion.id}/requirements`, { requirement_id: target.id, revision: target.revision, version_revision: scopedVersion.revision })
    const denied = await request.get(`/api/v1/requirements/${hidden.id}`, { headers: { Authorization: `Bearer ${selfA.token}` } })
    expect(denied.status()).toBe(404)
    const selfContext = await browser.newContext()
    try {
      const selfPage = await selfContext.newPage()
      await login(selfPage, selfA.username, selfA.password)
      await selfPage.setViewportSize({ width: 390, height: 900 })
      await selfPage.goto(`/#/versions/${scopedVersion.id}`)
      const worklist = selfPage.locator('.section-card').filter({ has: selfPage.getByRole('heading', { name: '需求清单', exact: true }) })
      await expect(worklist).toContainText(own.title)
      await expect(worklist).toContainText(createdBy.title)
      await expect(worklist).not.toContainText(hidden.title)
      await expect(worklist).toContainText('可见需求进度 0 / 2')
      await selfPage.getByRole('button', { name: '添加需求', exact: true }).click()
      await selfPage.getByRole('dialog', { name: '添加需求', exact: true }).getByRole('button', { name: '选择需求' }).click()
      const select = selfPage.getByRole('dialog', { name: '选择需求', exact: true })
      await select.getByRole('textbox', { name: '搜索需求' }).fill(prefix)
      await expect(select.locator('.selector-option')).toHaveCount(2)
      await expect(select).toContainText(own.title)
      await expect(select).toContainText(createdBy.title)
      await expect(select).not.toContainText(hidden.title)
      await select.getByRole('textbox', { name: '搜索需求' }).fill(hidden.title)
      await expect(select.getByText('暂无可见结果')).toBeVisible()
      await select.getByRole('button', { name: '取消', exact: true }).click()
      await expect(select).not.toBeVisible()
    } finally { await selfContext.close() }
    const paths = ['/', '/feedbacks', `/feedbacks/${feedback.id}`, '/requirements', `/requirements/${requirement.id}`, '/versions', `/versions/${version.id}`, '/releases', `/releases/${releaseId}`, '/notifications', '/profile', '/admin/audits', '/system/users', '/admin/roles', '/admin/systems']
    for (const width of [375, 390, 768, 1280, 1440]) {
      await admin.setViewportSize({ width, height: 900 })
      for (const path of paths) {
        await admin.goto(`/#${path}`)
        await expect(admin.locator('h1').first()).toBeVisible()
        await expect(admin.locator('.el-loading-mask:visible')).toHaveCount(0)
        await expect(admin.getByText('无权访问', { exact: true })).toHaveCount(0)
        await expect.poll(() => admin.evaluate(() => document.documentElement.scrollWidth), { message: `${width}px ${path}` }).toBeLessThanOrEqual(width + 1)
      }
      if (width < 768) {
        await admin.goto('/#/versions')
        await admin.getByRole('button', { name: '筛选', exact: true }).click()
        const drawer = admin.getByRole('dialog', { name: '筛选版本' })
        await expect(drawer).toBeVisible()
        await drawer.locator('.el-date-editor input').first().click()
        await expect(admin.locator('.el-picker__popper:visible')).toHaveCount(1)
        await expect.poll(() => admin.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
        await admin.keyboard.press('Escape')
        await expect(admin.locator('.el-picker__popper:visible')).toHaveCount(0)
        await admin.keyboard.press('Escape')
        await expect(drawer).toHaveCount(0)
      }
    }
    expect(errors).toEqual([])
  } finally {
    await Promise.all(contexts.map(context => context.close()))
  }
})
