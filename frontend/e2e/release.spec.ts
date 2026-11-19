import { randomUUID } from 'node:crypto'
import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test'

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
  await expect(page.getByRole('heading', { name: '我的工作台' })).toBeVisible()

  await page.goto('/#/feedbacks')
  await expect(page.getByRole('heading', { name: '反馈中心' })).toBeVisible()
  await page.goto('/#/feedbacks/new')
  const title = `发布验收反馈-${Date.now()}`
  await page.locator('.el-form-item').filter({ hasText: '标题' }).locator('input').fill(title)
  await page.locator('.el-form-item').filter({ hasText: '详细描述' }).locator('textarea').fill('生产构建浏览器验收反馈')
  await page.locator('.el-form-item').filter({ hasText: '反馈接收人' }).locator('.el-select__wrapper').click()
  await page.getByRole('option').first().click()
  await page.keyboard.press('Escape')
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
  await expect(page.getByRole('heading', { name: '我的工作台' })).toBeVisible()
}

async function status(page: Page, label: string, path: string) {
  await page.getByRole('button', { name: label, exact: true }).click()
  const dialog = page.getByRole('dialog', { name: label, exact: true })
  const response = page.waitForResponse(r => r.url().endsWith(`/api/v1${path}/status`) && r.request().method() === 'PATCH')
  await dialog.getByRole('button', { name: '确定', exact: true }).click()
  expect((await response).status()).toBe(200)
  await expect(dialog).toHaveCount(0)
}

async function selectPerson(page: Page, field: Locator, person: string, dismissWith: Locator) {
  await field.locator('.el-select__wrapper').click()
  const selector = field.getByRole('combobox')
  const listId = await selector.getAttribute('aria-controls')
  expect(listId).toBeTruthy()
  const list = page.locator(`[id="${listId}"]`)
  await selector.fill(person)
  await list.getByRole('option', { name: person, exact: true }).click()
  await dismissWith.click()
  await expect(list).toBeHidden()
}

test('Phase 7 real restricted users: presence, conflict, publish, notification and all viewports', async ({ browser, request }) => {
  test.setTimeout(300_000)
  // This file runs sequentially: the existing first test changes the disposable admin password.
  const adminName = process.env.INIT_ADMIN_USERNAME!
  const adminPassword = process.env.ITERFLOW_BROWSER_NEW_PASSWORD!
  const adminLogin = await request.post('/api/v1/auth/login', { data: { username: adminName, password: adminPassword } })
  expect(adminLogin.status()).toBe(200)
  const adminToken = (await adminLogin.json()).access_token as string
  const adminUser = await api(request, adminToken, 'GET', '/auth/me')
  const permissions: { id: number; code: string; deprecated: boolean }[] = await api(request, adminToken, 'GET', '/roles/permissions')
  const suffix = randomUUID().slice(0, 8)
  const system = await api(request, adminToken, 'POST', '/systems', { code: `P7_${suffix}`, name: `主链系统 ${suffix}` })
  async function user(name: string, scope: 'SELF' | 'ALL', codes: string[]) {
    const role = await api(request, adminToken, 'POST', '/roles', {
      code: `P7_${name}_${suffix}`, name: `P7 ${name}`, data_scope: scope,
      permission_ids: permissions.filter(p => codes.includes(p.code)).map(p => p.id),
    })
    const password = randomUUID()
    const username = `p7-${name}-${suffix}`
    const created = await api(request, adminToken, 'POST', '/users', { username, display_name: `P7 ${name} ${suffix}`, password, role_ids: [role.id] })
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
    await submit.locator('.el-form-item').filter({ hasText: '反馈接收人' }).getByRole('combobox').fill(`P7 A ${suffix}`)
    await submit.getByRole('option', { name: `P7 A ${suffix}`, exact: true }).click()
    await submit.keyboard.press('Escape')
    const created = submit.waitForResponse(r => r.url().endsWith('/api/v1/feedbacks') && r.request().method() === 'POST')
    await submit.getByRole('button', { name: '提交', exact: true }).click()
    const feedback = await (await created).json()
    expect(feedback.system_id).toBeNull()
    expect(feedback.status).toBe('NEW')
    await expect(submit).toHaveURL(new RegExp(`#/feedbacks/${feedback.id}$`))
    const feedbackWrites: string[] = []
    pageA.on('request', request => {
      const path = new URL(request.url()).pathname
      const feedbackPath = `/api/v1/feedbacks/${feedback.id}`
      if ((path === feedbackPath || path.startsWith(`${feedbackPath}/`)) && ['PATCH', 'POST', 'PUT', 'DELETE'].includes(request.method())) {
        feedbackWrites.push(`${request.method()} ${path}`)
      }
    })
    await pageA.goto(`/#/feedbacks/${feedback.id}`)
    await pageA.getByRole('button', { name: '受理并转需求', exact: true }).click()
    const createRequirement = pageA.getByRole('dialog', { name: '受理并转需求', exact: true })
    const requirementTitle = createRequirement.getByRole('textbox', { name: /^\*?标题$/ })
    await expect(requirementTitle).toHaveValue(title)
    await createRequirement.locator('.el-form-item').filter({ hasText: '业务系统' }).locator('.el-select').click()
    await pageA.getByRole('option', { name: system.name, exact: true }).click()
    await selectPerson(pageA, createRequirement.locator('[data-field="confirm"]'), `P7 B ${suffix}`, requirementTitle)
    await expect(createRequirement.getByRole('textbox', { name: /受理原因/ })).toHaveCount(0)
    const convertPath = `/api/v1/feedbacks/${feedback.id}/accept-and-convert`
    const converted = pageA.waitForResponse(r => r.url().endsWith(convertPath) && r.request().method() === 'POST')
    // Finish the conversion navigation's first detail read before assignment/reload.
    // URL changes alone do not mean that the detail response body is available.
    const initialDetail = pageA.waitForResponse(r => /\/api\/v1\/requirements\/\d+$/.test(r.url()) && r.request().method() === 'GET').then(r => r.json())
    await createRequirement.getByRole('button', { name: '受理并创建需求', exact: true }).click()
    const conversionResponse = await converted
    expect(conversionResponse.ok()).toBeTruthy()
    expect(conversionResponse.request().postDataJSON()).toMatchObject({
      type: 'CREATE_NEW', system_id: system.id, accept_on_convert: true, revision: feedback.revision,
      participants: expect.arrayContaining([{ user_id: b.id, role: 'CONFIRM' }]),
    })
    expect(conversionResponse.request().postDataJSON()).not.toHaveProperty('accept_reason')
    const requirement = await conversionResponse.json()
    expect(requirement.system_id).toBe(system.id)
    const linkedFeedback = await api(request, a.token, 'GET', `/feedbacks/${feedback.id}`)
    expect(linkedFeedback).toMatchObject({ system_id: null, main_requirement_id: requirement.id, status: 'REQUIREMENT_LINKED', revision: feedback.revision + 1 })
    const collaboration = await api(request, a.token, 'GET', `/feedbacks/${feedback.id}/collaboration`)
    expect(collaboration).toMatchObject({ handler_id: a.id, accepted_by: a.id, accepted_at: expect.any(String), revision: linkedFeedback.revision })
    expect(Number.isNaN(Date.parse(collaboration.accepted_at))).toBe(false)
    const sources = await api(request, a.token, 'GET', `/requirements/${requirement.id}/feedbacks`)
    expect(sources).toEqual([expect.objectContaining({ feedback_id: feedback.id, status: 'REQUIREMENT_LINKED', is_primary: true })])
    const feedbackAudits = await api(request, a.token, 'GET', `/audits?entity_type=FEEDBACK&entity_id=${feedback.id}`)
    expect(feedbackAudits.items.filter((row: { action: string }) => row.action === 'CONVERT_REQUIREMENT')).toEqual([
      expect.objectContaining({
        operator: expect.objectContaining({ id: a.id }), before: { status: 'NEW' },
        after: expect.objectContaining({ accept_on_convert: true, accept_reason: null, accepted_by: a.id, requirement_id: requirement.id }),
      }),
    ])
    expect(feedbackWrites).toEqual([`POST ${convertPath}`])
    await expect(pageA).toHaveURL(new RegExp(`#/requirements/${requirement.id}\\?return_to=%2Ffeedbacks$`))
    const initialRequirement = await initialDetail
    expect(initialRequirement.id).toBe(requirement.id)
    expect(initialRequirement.revision).toBe(requirement.revision)
    expect(initialRequirement.system_id).toBe(system.id)
    const requirementPath = `/requirements/${requirement.id}`
    const workflowPath = `${requirementPath}/workflow`
    const before = await api(request, b.token, 'GET', workflowPath)
    const rejected = await request.post(`/api/v1${workflowPath}`, {
      data: { action: 'CONFIRM', revision: requirement.revision },
      headers: { Authorization: `Bearer ${b.token}` },
    })
    expect(rejected.status()).toBe(409)
    expect(await api(request, b.token, 'GET', workflowPath)).toEqual(before)
    expect(await api(request, b.token, 'GET', `/requirements/${requirement.id}`)).toMatchObject({ status: 'DRAFT', revision: requirement.revision })
    await pageB.goto(`/#/requirements/${requirement.id}`)
    const arrange = pageB.getByRole('button', { name: '设置开发与验收人员', exact: true })
    await expect(arrange).toBeVisible()
    await expect(pageB.getByText(/尚未设置有效的开发人员、验收人员，暂不能确认当前内容/)).toBeVisible()
    await expect(pageB.getByRole('button', { name: '确认当前内容', exact: true })).toHaveCount(0)
    await arrange.click()
    const assignment = pageB.getByRole('dialog', { name: '安排设计、开发与验收人员', exact: true })
    const assignmentHint = assignment.getByText('保存人员后，仍需由对应人员执行确认或阶段操作。', { exact: true })
    for (const [role, name] of [['DEVELOP', 'A'], ['DEVELOP', 'B'], ['ACCEPT', 'B']]) {
      await selectPerson(pageB, assignment.locator(`[data-role="${role}"]`), `P7 ${name} ${suffix}`, assignmentHint)
    }
    const assignedPeople = pageB.waitForResponse(r => r.url().endsWith(`/requirements/${requirement.id}/participants`) && r.request().method() === 'PUT')
    await assignment.getByRole('button', { name: '保存人员', exact: true }).click()
    const peopleResponse = await assignedPeople
    expect(peopleResponse.status()).toBe(200)
    expect(peopleResponse.request().postDataJSON()).toMatchObject({ revision: requirement.revision })
    const people = await peopleResponse.json()
    expect(people.participants).toEqual(expect.arrayContaining([
      expect.objectContaining({ user_id: b.id, role: 'CONFIRM', active: true }),
      expect.objectContaining({ user_id: a.id, role: 'DEVELOP', active: true }),
      expect.objectContaining({ user_id: b.id, role: 'DEVELOP', active: true }),
      expect.objectContaining({ user_id: b.id, role: 'ACCEPT', active: true }),
    ]))
    await expect(assignment).toHaveCount(0)
    await expect(pageB.getByRole('button', { name: '确认当前内容', exact: true })).toBeVisible()
    const assigned = await api(request, a.token, 'PATCH', `/requirements/${requirement.id}`, { priority: 'P1', revision: people.revision })
    // Reload after API setup and verify both editors have fetched the assigned revision.
    const loadedA = pageA.waitForResponse(r => r.url().endsWith(`/requirements/${requirement.id}`) && r.request().method() === 'GET').then(r => r.json())
    await pageA.reload()
    expect((await loadedA).revision).toBe(assigned.revision)
    const loadedB = pageB.waitForResponse(r => r.url().endsWith(`/requirements/${requirement.id}`) && r.request().method() === 'GET').then(r => r.json())
    await pageB.reload()
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
    await expect(editB.getByText(`P7 A ${suffix} 正在编辑此需求`)).toBeVisible()
    await expect(editB.getByRole('button', { name: '保存' })).toBeEnabled()
    const titleInput = (page: Page) => page.getByRole('dialog', { name: '编辑需求' }).getByRole('textbox', { name: /^\*?标题$/, exact: true })
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
    await pageA.reload()
    await pageA.getByRole('button', { name: '创建版本', exact: true }).click()
    const versionForm = pageA.getByRole('dialog', { name: '创建版本并关联需求', exact: true })
    await expect(versionForm.locator('.el-form-item').filter({ hasText: '版本名称' }).locator('input')).toHaveValue(`${title} reviewed B`)
    await versionForm.getByPlaceholder('如 V1.0.0').fill(`P7-${suffix}`)
    const createdVersion = pageA.waitForResponse(r => r.url().endsWith('/api/v1/versions') && r.request().method() === 'POST')
    await versionForm.getByRole('button', { name: '创建并关联', exact: true }).click()
    const versionResponse = await createdVersion
    expect(versionResponse.status()).toBe(200)
    expect(versionResponse.request().postDataJSON()).toMatchObject({ requirement_id: requirement.id, requirement_revision: assigned.revision + 2 })
    const version = await versionResponse.json()
    expect(version.status).toBe('PLANNING')
    await expect(versionForm).toHaveCount(0)
    await expect(pageA.getByRole('button', { name: '创建版本', exact: true })).toHaveCount(0)
    expect((await api(request, a.token, 'GET', `/requirements/${requirement.id}`)).current_version_id).toBe(version.id)
    expect((await api(request, a.token, 'GET', `/releases?version_id=${version.id}`)).total).toBe(0)
    await pageB.reload()
    await pageB.getByRole('button', { name: '展开需求进度', exact: true }).click()
    await pageB.getByRole('button', { name: '确认当前内容', exact: true }).click()
    const confirmation = pageB.waitForResponse(r => r.url().endsWith(workflowPath) && r.request().method() === 'POST')
    await pageB.getByRole('dialog', { name: '确认当前内容', exact: true }).getByRole('button', { name: '确认操作' }).click()
    expect((await confirmation).status()).toBe(200)
    await expect(pageB.getByRole('dialog', { name: '确认当前内容', exact: true })).toHaveCount(0)
    await expect(assignment).toHaveCount(0)
    expect((await api(request, b.token, 'GET', requirementPath)).status).toBe('CONFIRMED')
    await status(pageB, '开始开发', requirementPath)
    const directLabel = '开发完成并验收通过'
    const beforeCompletion = await api(request, b.token, 'GET', workflowPath)
    await pageA.reload()
    await expect(pageA.getByRole('button', { name: '提交验收', exact: true })).toBeEnabled()
    await expect(pageA.getByRole('button', { name: directLabel, exact: true })).toHaveCount(0)
    const completionPayload = { action: 'COMPLETE_AND_ACCEPT', revision: beforeCompletion.revision }
    const developerOnly = await request.post(`/api/v1${workflowPath}`, {
      data: completionPayload, headers: { Authorization: `Bearer ${a.token}` },
    })
    expect(developerOnly.status()).toBe(403)
    expect(await api(request, b.token, 'GET', workflowPath)).toEqual(beforeCompletion)
    expect(await api(request, b.token, 'GET', requirementPath)).toMatchObject({ status: 'DEVELOPING', revision: beforeCompletion.revision })

    await pageB.getByRole('button', { name: directLabel, exact: true }).click()
    const completionDialog = pageB.getByRole('dialog', { name: directLabel, exact: true })
    await expect(completionDialog.getByText('提交后，需求将进入待发布。', { exact: true })).toBeVisible()
    const completed = pageB.waitForResponse(r => r.url().endsWith(workflowPath) && r.request().method() === 'POST')
    await completionDialog.getByRole('button', { name: '确认操作', exact: true }).click()
    const completionResponse = await completed
    expect(completionResponse.status()).toBe(200)
    expect(completionResponse.request().postDataJSON()).toMatchObject(completionPayload)
    const completedWorkflow = await completionResponse.json()
    expect(completedWorkflow.revision).toBe(beforeCompletion.revision + 1)
    const completionSteps = completedWorkflow.records.filter((record: { action: string }) => ['STATUS_TESTING', 'STATUS_DONE'].includes(record.action))
    expect(completionSteps).toHaveLength(2)
    expect(completionSteps).toEqual(expect.arrayContaining([
      expect.objectContaining({ action: 'STATUS_TESTING', actor_id: b.id, detail: expect.objectContaining({ from: 'DEVELOPING', to: 'TESTING', source: 'COMPLETE_AND_ACCEPT' }) }),
      expect.objectContaining({ action: 'STATUS_DONE', actor_id: b.id, detail: expect.objectContaining({ from: 'TESTING', to: 'DONE', source: 'COMPLETE_AND_ACCEPT' }) }),
    ]))
    await expect(completionDialog).toBeHidden()
    await expect(pageB.locator('.requirement-progress .progress-status')).toHaveText('待发布')
    expect(await api(request, b.token, 'GET', requirementPath)).toMatchObject({ status: 'DONE', revision: completedWorkflow.revision })
    await pageA.goto(`/#/versions/${version.id}`)
    expect((await api(request, a.token, 'GET', `/versions/${version.id}`)).status).toBe('READY')
    for (const label of ['开始开发', '提测', '待发布', '退回测试']) {
      await expect(pageA.getByRole('button', { name: label, exact: true })).toHaveCount(0)
    }
    await pageA.getByRole('button', { name: '发布版本', exact: true }).click()
    const publishDialog = pageA.getByRole('dialog', { name: '发布版本' })
    await expect(publishDialog.getByRole('button', { name: '确认发布' })).toBeEnabled()
    await publishDialog.locator('.el-form-item').filter({ hasText: '发布说明' }).locator('textarea').fill('Phase 7 real browser release')
    const current = await api(request, a.token, 'GET', `/requirements/${requirement.id}`)
    // A real concurrent business change invalidates an already displayed successful publish check.
    await api(request, a.token, 'PATCH', `${requirementPath}/status`, { status: 'DEVELOPING', revision: current.revision, reason: 'Phase 7 concurrent publish check' })
    const business = pageA.waitForResponse(r => r.url().endsWith(`/versions/${version.id}/publish`) && r.request().method() === 'POST')
    await publishDialog.getByRole('button', { name: '确认发布' }).click()
    const businessResponse = await business
    expect(businessResponse.status()).toBe(409)
    expect((await businessResponse.json()).code).toBe(40923)
    await expect(pageA.getByText('发布检查未通过', { exact: true })).toBeVisible()
    await expect(pageA.getByRole('dialog', { name: '数据已被其他用户修改' })).toHaveCount(0)
    await expect(publishDialog).toBeVisible()
    expect((await api(request, a.token, 'GET', `/releases?version_id=${version.id}`)).total).toBe(0)
    await pageB.reload()
    for (const label of ['提交验收', '验收通过']) await status(pageB, label, requirementPath)
    await pageA.reload()
    await pageA.getByRole('button', { name: '发布版本', exact: true }).click()
    await publishDialog.locator('.el-form-item').filter({ hasText: '发布说明' }).locator('textarea').fill('Phase 7 real browser release')
    await expect(publishDialog.getByRole('button', { name: '确认发布' })).toBeEnabled()
    const published = pageA.waitForResponse(r => r.url().endsWith(`/versions/${version.id}/publish`) && r.request().method() === 'POST')
    await publishDialog.getByRole('button', { name: '确认发布' }).click()
    const result = await (await published).json()
    expect(result.release.result).toBe('SUCCESS')
    const releaseId = result.release.id as number
    await expect(publishDialog).toHaveCount(0)
    const releaseHistory = pageA.locator('.section-card').filter({ has: pageA.getByRole('heading', { name: '发布历史', exact: true }) })
    await releaseHistory.getByRole('button', { name: '查看发布详情', exact: true }).click()
    const releaseDrawer = pageA.getByRole('dialog', { name: '发布记录详情', exact: true })
    await expect(releaseDrawer.getByText('Phase 7 real browser release', { exact: true })).toBeVisible()
    await releaseDrawer.getByRole('button', { name: '打开完整页面', exact: true }).click()
    await expect(pageA).toHaveURL(new RegExp(`#/releases/${releaseId}(?:\\?|$)`))
    await expect(pageA.getByRole('heading', { name: '发布记录详情', exact: true })).toBeVisible()
    await expect(pageA.getByText('Phase 7 real browser release', { exact: true })).toBeVisible()
    for (const label of ['编辑', '删除', '回滚']) await expect(pageA.getByRole('button', { name: label, exact: true })).toHaveCount(0)
    expect((await api(request, a.token, 'GET', `/requirements/${requirement.id}`)).status).toBe('ONLINE')
    expect((await api(request, submitter.token, 'GET', `/feedbacks/${feedback.id}`)).status).toBe('ONLINE')

    // Both passes notify on development start and acceptance. The combined action
    // records the submission for acceptance without sending its intermediate notice.
    const onlineTitle = `反馈 ${feedback.feedback_no} 已上线`
    const feedbackNoticeTitles = [
      onlineTitle,
      `反馈 #${feedback.id} · 反馈已关联需求`,
      `反馈 #${feedback.id} · 关联需求进度更新: 需求已提交验收`,
      ...['需求进入开发', '需求验收通过, 等待发布'].flatMap(label => [
        `反馈 #${feedback.id} · 关联需求进度更新: ${label}`,
        `反馈 #${feedback.id} · 关联需求进度更新: ${label}`,
      ]),
    ].sort()
    async function feedbackNotices() {
      const rows: { entity_type: string; entity_id: number; title: string; read_at: string | null }[] = await api(request, submitter.token, 'GET', '/notifications')
      return rows.filter(row => row.entity_type === 'FEEDBACK' && row.entity_id === feedback.id)
    }
    await expect.poll(async () => (await feedbackNotices()).map(row => row.title).sort(), { timeout: 30_000 }).toEqual(feedbackNoticeTitles)
    await submit.goto('/#/notifications')
    const notification = submit.locator('.notification-card').filter({ hasText: onlineTitle })
    await expect(notification).toBeVisible()
    const marked = submit.waitForResponse(r => /\/notifications\/\d+\/read$/.test(r.url()))
    await notification.click()
    expect((await marked).status()).toBe(200)
    await expect(submit).toHaveURL(new RegExp(`#/feedbacks/${feedback.id}$`))
    expect((await feedbackNotices()).find(row => row.title === onlineTitle)?.read_at).toEqual(expect.any(String))
    await api(request, submitter.token, 'POST', '/notifications/read-all')
    await expect.poll(async () => (await api(request, submitter.token, 'GET', '/notifications/unread-count')).unread_count).toBe(0)
    const audits = await api(request, a.token, 'GET', `/audits?entity_type=VERSION&entity_id=${version.id}`)
    expect(audits.items.some((row: { action: string }) => row.action === 'VERSION_PUBLISH')).toBeTruthy()

    const reviewPath = `${requirementPath}/online-review`
    const releasePath = `/releases?version_id=${version.id}`
    const releaseBeforeReview = await api(request, a.token, 'GET', releasePath)
    expect(releaseBeforeReview).toMatchObject({ total: 1, items: [expect.objectContaining({ id: releaseId, result: 'SUCCESS' })] })
    const sourceBeforeReview = await api(request, a.token, 'GET', `${requirementPath}/feedbacks`)
    const feedbackBeforeReview = await api(request, submitter.token, 'GET', `/feedbacks/${feedback.id}`)
    const publishedReview = await api(request, a.token, 'GET', reviewPath)
    expect(publishedReview).toMatchObject({ can_confirm: true, confirmation: null, feedbacks: [], feedback_total: 0 })

    const reviewCard = (page: Page) => page.locator('.section-card').filter({ has: page.getByRole('heading', { name: '线上效果确认', exact: true }) })
    const confirmLabel = '确认无误'
    const followupLabel = '提交线上反馈'
    await pageB.setViewportSize({ width: 1440, height: 900 })
    const publishedDetail = pageB.waitForResponse(r => r.url().endsWith(`/api/v1${requirementPath}`) && r.request().method() === 'GET').then(r => r.json())
    await pageB.reload()
    expect(await publishedDetail).toMatchObject({ status: 'ONLINE', revision: publishedReview.revision })
    await expect(reviewCard(pageB).getByText('待确认', { exact: true })).toBeVisible()
    await expect(reviewCard(pageB).getByRole('button', { name: confirmLabel, exact: true })).toBeDisabled()
    const nonCreator = await request.post(`/api/v1${reviewPath}/confirm`, {
      data: { revision: publishedReview.revision }, headers: { Authorization: `Bearer ${b.token}` },
    })
    expect(nonCreator.status()).toBe(403)

    await pageA.setViewportSize({ width: 375, height: 900 })
    await pageA.goto(`/#${requirementPath}`)
    await reviewCard(pageA).getByRole('button', { name: confirmLabel, exact: true }).click()
    const confirmDialog = pageA.getByRole('dialog', { name: '确认线上效果', exact: true })
    const note = '已在生产形态验收环境检查线上效果。'
    await confirmDialog.getByRole('textbox', { name: /确认说明/ }).fill(note)
    const laterRequirement = await api(request, b.token, 'PATCH', requirementPath, { priority: 'P2', revision: publishedReview.revision })
    const post = (page: Page, path: string) => page.waitForResponse(r => r.url().endsWith(`/api/v1${path}`) && r.request().method() === 'POST')
    const staleReview = post(pageA, `${reviewPath}/confirm`)
    await confirmDialog.getByRole('button', { name: confirmLabel, exact: true }).click()
    const staleReviewResponse = await staleReview
    expect(staleReviewResponse.status()).toBe(409)
    expect((await staleReviewResponse.json()).code).toBe(40910)
    await confirmDialog.getByRole('button', { name: '刷新需求信息', exact: true }).click()
    await expect(confirmDialog.getByRole('textbox', { name: /确认说明/ })).toHaveValue(note)
    const confirmedOnline = post(pageA, `${reviewPath}/confirm`)
    await confirmDialog.getByRole('button', { name: confirmLabel, exact: true }).click()
    const confirmedResponse = await confirmedOnline
    expect(confirmedResponse.status()).toBe(200)
    expect(confirmedResponse.request().postDataJSON()).toEqual({ revision: laterRequirement.revision, note })
    const onlineConfirmation = await confirmedResponse.json()
    expect(onlineConfirmation).toMatchObject({ confirmed_by: a.id, confirmed_by_name: `P7 A ${suffix}`, confirmed_at: expect.any(String), note })
    expect(Number.isNaN(Date.parse(onlineConfirmation.confirmed_at))).toBe(false)
    await expect(confirmDialog).toBeHidden()
    await expect(reviewCard(pageA).getByText(note, { exact: true })).toBeVisible()
    await expect(reviewCard(pageA).getByRole('button', { name: confirmLabel, exact: true })).toHaveCount(0)

    const recordedReview = await api(request, a.token, 'GET', reviewPath)
    const repeated = await request.post(`/api/v1${reviewPath}/confirm`, {
      data: { revision: recordedReview.revision, note: '尝试覆盖' }, headers: { Authorization: `Bearer ${a.token}` },
    })
    expect(repeated.status()).toBe(409)

    const followupTitle = `线上使用反馈 ${suffix}`
    await reviewCard(pageA).getByRole('button', { name: followupLabel, exact: true }).click()
    const followupDialog = pageA.getByRole('dialog', { name: followupLabel, exact: true })
    const followupTitleField = followupDialog.locator('.el-form-item').filter({ hasText: '标题' }).getByRole('textbox')
    await followupTitleField.fill(followupTitle)
    await followupDialog.locator('.el-form-item').filter({ hasText: '详细描述' }).getByRole('textbox').fill('正常使用后发现仍可改善的情况。')
    await selectPerson(pageA, followupDialog.locator('.el-form-item').filter({ hasText: '反馈接收人' }), `P7 B ${suffix}`, followupTitleField)
    const createdFollowup = post(pageA, `${reviewPath}/feedbacks`)
    await followupDialog.getByRole('button', { name: '提交', exact: true }).click()
    const followupResponse = await createdFollowup
    expect(followupResponse.status()).toBe(200)
    expect(followupResponse.request().postDataJSON()).toMatchObject({ revision: recordedReview.revision, title: followupTitle, recipient_ids: [b.id] })
    const followup = await followupResponse.json()
    expect(followup).toMatchObject({ status: 'NEW', main_requirement_id: null, submitter_id: a.id })
    const feedbackPath = `/feedbacks/${followup.id}`
    const followupCollaboration = await api(request, b.token, 'GET', `${feedbackPath}/collaboration`)
    expect(followupCollaboration).toMatchObject({ recipients: [expect.objectContaining({ id: b.id })], handler_id: null, accepted_at: null })
    await expect(followupDialog).toBeHidden()
    await expect(reviewCard(pageA).getByRole('link', { name: new RegExp(followupTitle) })).toBeVisible()
    await expect.poll(() => pageA.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(376)
    await expect(pageA.locator('.requirement-detail > .el-loading-mask')).toBeHidden()
    await expect(pageA.locator('.el-message')).toHaveCount(0)
    await pageA.screenshot({ path: test.info().outputPath('online-review-real-375.png'), fullPage: true })

    await pageB.reload()
    await expect(reviewCard(pageB).getByText(note, { exact: true })).toBeVisible()
    await expect(reviewCard(pageB).getByRole('link', { name: new RegExp(followupTitle) })).toBeVisible()
    await expect.poll(() => pageB.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(1441)
    await expect(pageB.locator('.requirement-detail > .el-loading-mask')).toBeHidden()
    await pageB.screenshot({ path: test.info().outputPath('online-review-real-1440.png'), fullPage: true })
    expect(await api(request, a.token, 'GET', reviewPath)).toMatchObject({
      confirmation: onlineConfirmation, can_confirm: false, feedbacks: [expect.objectContaining({ id: followup.id, title: followupTitle, status: 'NEW' })], feedback_total: 1,
    })
    expect(await api(request, a.token, 'GET', `${requirementPath}/feedbacks`)).toEqual(sourceBeforeReview)
    expect(await api(request, submitter.token, 'GET', `/feedbacks/${feedback.id}`)).toEqual(feedbackBeforeReview)
    expect(await api(request, a.token, 'GET', releasePath)).toEqual(releaseBeforeReview)
    expect(await api(request, a.token, 'GET', requirementPath)).toMatchObject({ status: 'ONLINE', current_version_id: version.id })

    // V1.8: exercise the new selector/worklist against real SELF repositories,
    // including owner visibility, creator visibility and another account's object.
    const selfCodes = ['dashboard.view', 'rd.requirement.view', 'rd.requirement.create', 'rd.version.view', 'rd.version.edit']
    const selfA = await user('SelfA', 'SELF', selfCodes)
    const selfB = await user('SelfB', 'SELF', selfCodes)
    const prefix = `V18 scoped ${suffix}`
    const adminConfirmer = { user_id: adminUser.id, role: 'CONFIRM' }
    const own = await api(request, adminToken, 'POST', '/requirements', { title: `${prefix} owner A`, system_id: system.id, requirement_type: 'FEATURE', priority: 'P0', description: 'Participant scope', participants: [adminConfirmer, { user_id: selfA.id, role: 'DEVELOP' }] })
    const createdBy = await api(request, selfA.token, 'POST', '/requirements', { title: `${prefix} creator A`, system_id: system.id, requirement_type: 'FEATURE', priority: 'P1', description: 'Creator scope', participants: [adminConfirmer] })
    const hidden = await api(request, adminToken, 'POST', '/requirements', { title: `${prefix} private B`, system_id: system.id, requirement_type: 'FEATURE', priority: 'P2', description: 'Out of scope', participants: [adminConfirmer, { user_id: selfB.id, role: 'DEVELOP' }] })
    let scopedVersion = await api(request, adminToken, 'POST', '/versions', { version_no: `V18-${suffix}`, name: prefix, system_id: system.id, owner_id: selfA.id })
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
      await expect(worklist).toContainText('0 / 2 项完成')
      await selfPage.getByRole('button', { name: '添加需求', exact: true }).click()
      const select = selfPage.getByRole('dialog', { name: '批量添加需求', exact: true })
      await select.getByPlaceholder('编号 / 标题').fill(prefix)
      await select.getByRole('button', { name: '搜索', exact: true }).click()
      await expect(select.getByRole('checkbox')).toHaveCount(2)
      await expect(select).toContainText(own.title)
      await expect(select).toContainText(createdBy.title)
      await expect(select).not.toContainText(hidden.title)
      await select.getByPlaceholder('编号 / 标题').fill(hidden.title)
      await select.getByRole('button', { name: '搜索', exact: true }).click()
      await expect(select.getByRole('checkbox')).toHaveCount(0)
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

test('real product announcement images and cross-session reading', async ({ browser, request }) => {
  const username = process.env.INIT_ADMIN_USERNAME, password = process.env.ITERFLOW_BROWSER_NEW_PASSWORD
  if (!username || !password) throw new Error('Isolated browser credentials required')
  const logged = await request.post('/api/v1/auth/login', { data: { username, password } })
  expect(logged.ok()).toBeTruthy()
  const pair = await logged.json(), token = pair.access_token
  const title = `产品更新验收-${randomUUID().slice(0,8)}`
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()
  await page.addInitScript(value => { localStorage.setItem('iterflow.access_token', value.access_token); localStorage.setItem('iterflow.refresh_token', value.refresh_token) }, pair)
  await page.goto('/#/announcements')
  await page.getByRole('button', { name: '新增公告', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '新增更新公告', exact: true })
  await dialog.getByRole('textbox', { name: '公告标题', exact: true }).fill(title)
  await dialog.getByRole('textbox', { name: '版本标识', exact: true }).fill('隔离验收版本')
  await dialog.locator('[contenteditable=true]').fill('新增公告支持截图及账号已读同步。')
  await dialog.getByText('重要更新：涉及流程变化或需要用户配合，登录后弹出提醒', { exact:true }).click()
  await expect(dialog.getByRole('checkbox')).toBeChecked()
  await dialog.locator('input[type=file]').setInputFiles({ name:'screenshot.png', mimeType:'image/png', buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j9eQAAAAASUVORK5CYII=', 'base64') })
  await dialog.getByRole('button', { name:'保存草稿', exact:true }).click()
  await expect(dialog).toBeHidden()
  await expect(page.getByRole('button', { name:'查看大图', exact:true })).toBeVisible()
  await page.getByRole('button', { name:'发布公告', exact:true }).click()
  await page.getByRole('button', { name:'确认发布', exact:true }).click()
  await expect(page.getByRole('dialog', {name:'发布更新公告',exact:true})).toBeHidden()
  const noticeUrl=page.url()
  const roles=await api(request,token,'GET','/roles')
  const member=roles.find((r:any)=>r.code==='MEMBER')
  const readerName='notice-reader-'+randomUUID().slice(0,8), initial='Test-'+randomUUID(), changed='Next-'+randomUUID()
  await api(request,token,'POST','/users',{username:readerName,display_name:'公告跨设备验收',password:initial,role_ids:[member.id]})
  const first=await request.post('/api/v1/auth/login',{data:{username:readerName,password:initial}})
  const readerToken=(await first.json()).access_token
  await api(request,readerToken,'POST','/auth/change-password',{current_password:initial,new_password:changed})
  const loginReader=async()=>{const result=await request.post('/api/v1/auth/login',{data:{username:readerName,password:changed}});expect(result.ok()).toBeTruthy();return await result.json()}
  const readerContext=await browser.newContext({viewport:{width:375,height:812}}), reader=await readerContext.newPage()
  await reader.addInitScript(value=>{localStorage.setItem('iterflow.access_token',value.access_token);localStorage.setItem('iterflow.refresh_token',value.refresh_token)},await loginReader())
  await reader.goto('/#/notifications')
  await expect(reader.getByRole('dialog',{name:'重要更新公告',exact:true})).toBeVisible()
  await reader.getByRole('button',{name:'我已知晓',exact:true}).click()
  await expect(reader.getByRole('dialog',{name:'重要更新公告',exact:true})).toBeHidden()
  const anotherContext=await browser.newContext(), another=await anotherContext.newPage()
  await another.addInitScript(value=>{localStorage.setItem('iterflow.access_token',value.access_token);localStorage.setItem('iterflow.refresh_token',value.refresh_token)},await loginReader())
  await another.goto('/#/notifications')
  await expect(another.getByRole('heading',{name:'通知中心',exact:true})).toBeVisible()
  await expect(another.getByRole('dialog',{name:'重要更新公告',exact:true})).toHaveCount(0)
  await reader.goto(noticeUrl)
  await expect(reader.getByRole('heading',{name:title,exact:true})).toBeVisible()
  await reader.getByRole('button',{name:'查看大图',exact:true}).click()
  await expect(reader.getByRole('dialog',{name:'公告图片大图',exact:true})).toBeVisible()
  await reader.getByRole('button',{name:'关闭',exact:true}).click()
  await expect(reader.getByRole('dialog',{name:'公告图片大图',exact:true})).toBeHidden()
  expect(await reader.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)
  await reader.screenshot({path:'test-results/announcement-real-mobile.png',fullPage:true})
  await page.screenshot({path:'test-results/announcement-real-desktop.png',fullPage:true})
  await context.close();await readerContext.close();await anotherContext.close()
})

test('Real target publishing: optional coverage and later multiple target records', async ({ page, request }) => {
  test.setTimeout(180_000)
  const username = process.env.INIT_ADMIN_USERNAME!
  const password = process.env.ITERFLOW_BROWSER_NEW_PASSWORD!
  const loginResult = await request.post('/api/v1/auth/login', { data: { username, password } })
  expect(loginResult.status()).toBe(200)
  const token = (await loginResult.json()).access_token as string
  const me = await api(request, token, 'GET', '/auth/me')
  const member = (await api(request, token, 'GET', '/roles')).find((role: { code: string }) => role.code === 'MEMBER')
  const otherAcceptor = await api(request, token, 'POST', '/users', {
    username: `mt-accept-${randomUUID().slice(0, 8)}`,
    display_name: '多目标发布原验收人', password: randomUUID(), role_ids: [member.id],
  })
  await login(page, username, password)
  for (const width of [1440, 375]) {
    await page.setViewportSize({ width, height: 1000 })
    const suffix = randomUUID().slice(0, 8)
    const system = await api(request, token, 'POST', '/systems', { code: `MT_${suffix}`, name: `多目标主链 ${suffix}` })
    const targetName = (code: string) => code === 'B' ? '真实 PC B' : `真实小程序 ${code}`
    for (const code of ['A', 'B', 'C']) await api(request, token, 'POST', `/systems/${system.id}/release-targets`, { code, name: targetName(code), platform: code === 'B' ? 'PC_WEB' : 'WECHAT_MINI_PROGRAM', app_id: code === 'B' ? null : `wx${suffix}${code}` })
    const created = await api(request, token, 'POST', '/requirements', {
      title: `多小程序需求 ${suffix}`, description: '仅用于本地合成流程验收', requirement_type: 'FEATURE', system_id: system.id,
      participants: [{ role: 'CONFIRM', user_id: me.id }, { role: 'DEVELOP', user_id: me.id }, { role: 'ACCEPT', user_id: otherAcceptor.id }],
    })
    const path = `/requirements/${created.id}`
    const confirmed = await api(request, token, 'POST', `${path}/workflow`, { revision: created.revision, action: 'CONFIRM' })
    const developing = await api(request, token, 'PATCH', `${path}/status`, { status: 'DEVELOPING', revision: confirmed.revision })
    await page.goto(`/#${path}`)
    await page.getByRole('button', { name: '展开需求进度', exact: true }).click()
    const progress = page.locator('.requirement-progress')
    await progress.getByRole('list', { name: '需求阶段' }).getByRole('button', { name: /^待开发/ }).click()
    await progress.getByRole('button', { name: '选择 / 调整人员', exact: true }).click()
    const people = page.getByRole('dialog', { name: '安排设计、开发与验收人员', exact: true })
    await people.getByRole('button', { name: '将开发人员加入验收', exact: true }).click()
    const savePeople = page.waitForResponse(r => r.url().endsWith(`${path}/participants`) && r.request().method() === 'PUT')
    await people.getByRole('button', { name: '保存人员', exact: true }).click()
    const assignment = await savePeople
    expect(assignment.status()).toBe(200)
    expect(assignment.request().postDataJSON()).toMatchObject({ revision: developing.revision })
    const { participants, revision } = await assignment.json()
    const acceptors = participants.filter((person: { role: string }) => person.role === 'ACCEPT')
    expect(acceptors).toHaveLength(2)
    expect(acceptors).toEqual(expect.arrayContaining([
      expect.objectContaining({ user_id: me.id, active: true }),
      expect.objectContaining({ user_id: otherAcceptor.id, active: true }),
    ]))
    await expect(people).toBeHidden()

    const directLabel = '开发完成并验收通过'
    await expect(progress.getByRole('button', { name: '提交验收', exact: true })).toBeEnabled()
    await progress.getByRole('button', { name: directLabel, exact: true }).click()
    const direct = page.getByRole('dialog', { name: directLabel, exact: true })
    const combined = page.waitForResponse(r => r.url().endsWith(`${path}/workflow`) && r.request().method() === 'POST')
    await direct.getByRole('button', { name: '确认操作', exact: true }).click()
    const completion = await combined
    expect(completion.status()).toBe(200)
    expect(completion.request().postDataJSON()).toMatchObject({ action: 'COMPLETE_AND_ACCEPT', revision })
    const workflow = await completion.json()
    expect(workflow.revision).toBe(revision + 1)
    const steps = workflow.records.filter((record: { action: string }) => ['STATUS_TESTING', 'STATUS_DONE'].includes(record.action))
    expect(steps).toHaveLength(2)
    expect(steps).toEqual(expect.arrayContaining([
      expect.objectContaining({ action: 'STATUS_TESTING', actor_id: me.id, detail: expect.objectContaining({ from: 'DEVELOPING', to: 'TESTING', source: 'COMPLETE_AND_ACCEPT' }) }),
      expect.objectContaining({ action: 'STATUS_DONE', actor_id: me.id, detail: expect.objectContaining({ from: 'TESTING', to: 'DONE', source: 'COMPLETE_AND_ACCEPT' }) }),
    ]))
    await expect(direct).toBeHidden()
    await expect(progress.locator('.progress-status')).toHaveText('待发布')
    const req = await api(request, token, 'GET', path)
    expect(req).toMatchObject({ status: 'DONE', revision: workflow.revision })
    const audits = await api(request, token, 'GET', `/audits?entity_type=REQUIREMENT&entity_id=${req.id}`)
    expect(audits.items.filter((row: { action: string; after?: { source?: string } }) => row.action === 'STATUS_CHANGE' && row.after?.source === 'COMPLETE_AND_ACCEPT')).toEqual([
      expect.objectContaining({ operator: expect.objectContaining({ id: me.id }), before: { status: 'DEVELOPING' }, after: expect.objectContaining({ via: 'TESTING', status: 'DONE' }) }),
    ])
    const version = await api(request, token, 'POST', '/versions', { version_no: `MT-${suffix}`, name: `多目标版本 ${suffix}`, system_id: system.id, requirement_id: req.id, requirement_revision: req.revision })
    await page.goto(`/#/versions/${version.id}`)
    await page.getByRole('button', { name: '发布版本', exact: true }).click()
    const publish = page.getByRole('dialog', { name: '发布版本', exact: true })
    const selectOnPublish = width === 1440
    if (selectOnPublish) await publish.locator('.el-checkbox').filter({ hasText: targetName('A') }).click()
    await publish.getByRole('textbox', { name: '发布说明', exact: true }).fill(selectOnPublish ? '先记 A，其他目标稍后补记' : '正常发布，所有目标稍后补记')
    await publish.getByRole('button', { name: '确认发布', exact: true }).click(); await expect(publish).toBeHidden()
    const released = await api(request, token, 'GET', `/releases?version_id=${version.id}`)
    expect(released.total).toBe(1)
    const current = await api(request, token, 'GET', `/requirements/${req.id}`)
    expect(current.status).toBe('ONLINE')
    const panel = page.locator('#release-target-batches')
    if (selectOnPublish) await expect(panel).toContainText('已记录 1 个平台 / PC 站点')
    expect((await api(request, token, 'GET', `/target-release-records?version_id=${version.id}`)).total).toBe(selectOnPublish ? 1 : 0)
    await panel.getByRole('button', { name: '补记已发布目标', exact: true }).click()
    const record = page.getByRole('dialog', { name: '补记已发布目标', exact: true })
    if (selectOnPublish) await expect(record.getByRole('checkbox', { name: /真实小程序 A/ })).toBeDisabled()
    for (const code of selectOnPublish ? ['B', 'C'] : ['A', 'B', 'C']) await record.locator('.el-checkbox').filter({ hasText: targetName(code) }).click()
    await record.getByRole('button', { name: '保存已发布目标', exact: true }).click(); await expect(record).toBeHidden()
    await expect(panel).toContainText('已记录 3 个平台 / PC 站点')
    expect((await api(request, token, 'GET', `/releases?version_id=${version.id}`)).items).toEqual(released.items)
    expect((await api(request, token, 'GET', `/target-release-records?version_id=${version.id}`)).total).toBe(3)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    await page.screenshot({ path: test.info().outputPath(`real-supplement-${width}.png`), fullPage: true })
  }
})
