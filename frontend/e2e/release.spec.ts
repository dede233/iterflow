import { expect, test } from '@playwright/test'

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

  await page.goto('/')
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

  await page.goto('/feedbacks')
  await expect(page.getByRole('heading', { name: '反馈中心' })).toBeVisible()
  await page.goto('/feedbacks/new')
  const title = `发布验收反馈-${Date.now()}`
  await page.locator('.el-form-item').filter({ hasText: '标题' }).locator('input').fill(title)
  await page.locator('.el-form-item').filter({ hasText: '详细描述' }).locator('textarea').fill('生产构建浏览器验收反馈')
  await page.getByRole('button', { name: '提交', exact: true }).click()
  await expect(page).toHaveURL(/\/feedbacks\/\d+$/)
  await page.goto('/feedbacks')
  await expect(page.getByText(title)).toBeVisible()
  expect(browserErrors).toEqual([])
})

test('V1.5 responsive release acceptance across core and administration pages', async ({ page }) => {
  const username = process.env.INIT_ADMIN_USERNAME
  const password = process.env.ITERFLOW_BROWSER_NEW_PASSWORD
  if (!username || !password) throw new Error('CI browser credentials are required')
  const browserErrors: string[] = []
  page.on('pageerror', (error) => browserErrors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text())
  })
  await page.goto('/login')
  await page.getByPlaceholder('用户名').fill(username)
  await page.getByPlaceholder('密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '首页 / 系统概览' })).toBeVisible()
  const token = await page.evaluate(() => localStorage.getItem('iterflow.access_token'))
  if (!token) throw new Error('Authenticated browser token not available')
  const headers = { Authorization: `Bearer ${token}` }
  const feedbackResponse = await page.request.post('/api/v1/feedbacks', {
    headers,
    data: {
      title: `RA-响应式反馈-${Date.now()}`,
      feedback_type: 'NEW_FEATURE',
      description: '五档视口真实生产构建验收',
    },
  })
  expect(feedbackResponse.ok()).toBeTruthy()
  const feedback = await feedbackResponse.json()
  const acceptedResponse = await page.request.patch(`/api/v1/feedbacks/${feedback.id}/status`, {
    headers,
    data: { status: 'ACCEPTED', revision: feedback.revision },
  })
  expect(acceptedResponse.ok()).toBeTruthy()
  const accepted = await acceptedResponse.json()
  const requirementResponse = await page.request.post(`/api/v1/feedbacks/${feedback.id}/convert`, {
    headers,
    data: {
      type: 'CREATE_NEW', revision: accepted.revision,
      requirement_title: `RA-响应式需求-${Date.now()}`,
      requirement_type: 'FEATURE', description: '五档视口需求详情验收',
    },
  })
  expect(requirementResponse.ok()).toBeTruthy()
  const requirement = await requirementResponse.json()
  const versionResponse = await page.request.post('/api/v1/versions', {
    headers,
    data: { version_no: `RA-${Date.now()}`, name: 'RA 响应式版本' },
  })
  expect(versionResponse.ok()).toBeTruthy()
  const version = await versionResponse.json()

  const corePages = [
    '/', '/feedbacks', '/feedbacks/new', `/feedbacks/${feedback.id}`,
    '/requirements', `/requirements/${requirement.id}`,
    '/versions', `/versions/${version.id}`, '/notifications', '/profile',
  ]
  const desktopPages = ['/releases', '/admin/audits', '/system/users', '/admin/roles']
  for (const width of [375, 390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    const paths = width < 1200 ? corePages : [...corePages, ...desktopPages]
    for (const path of paths) {
      await page.goto(path)
      await expect(page.locator('body')).toBeVisible()
      await expect(page).toHaveURL(new RegExp(path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$'))
      if (path === '/feedbacks/new') {
        await expect(page.getByRole('button', { name: '提交', exact: true })).toBeVisible()
      }
      const dimensions = await page.evaluate(() => ({
        document: document.documentElement.scrollWidth,
        viewport: window.innerWidth,
      }))
      expect(dimensions.document, `${width}px ${path} horizontal overflow`).toBeLessThanOrEqual(dimensions.viewport + 2)
    }
  }
  await page.goto('/profile')
  await page.getByRole('main').getByRole('button', { name: '修改密码' }).click()
  await expect(page).toHaveURL(/\/change-password\?from=profile$/)
  await expect(page.getByRole('heading', { name: '修改密码' })).toBeVisible()
  const updatedPassword = `${password}-updated`
  await page.locator('input[type="password"]').nth(0).fill(password)
  await page.locator('input[type="password"]').nth(1).fill(updatedPassword)
  await page.locator('input[type="password"]').nth(2).fill(updatedPassword)
  await page.getByRole('button', { name: '保存新密码' }).click()
  await expect(page).toHaveURL(/\/profile$/)
  const rotatedToken = await page.evaluate(() => localStorage.getItem('iterflow.access_token'))
  expect(rotatedToken).toBeTruthy()
  expect(rotatedToken).not.toBe(token)
  const me = await page.request.get('/api/v1/auth/me', {
    headers: { Authorization: `Bearer ${rotatedToken}` },
  })
  expect(me.status()).toBe(200)
  expect((await me.json()).username).toBe(username)
  const roles = await page.request.get('/api/v1/roles', {
    headers: { Authorization: `Bearer ${rotatedToken}` },
  })
  expect(roles.status()).toBe(200)
  const memberRole = (await roles.json()).find((role: { code: string }) => role.code === 'MEMBER')
  expect(memberRole).toBeTruthy()
  const memberUsername = `ra-member-${Date.now()}`
  const memberPassword = `${password}-member`
  const createdMember = await page.request.post('/api/v1/users', {
    headers: { Authorization: `Bearer ${rotatedToken}` },
    data: {
      username: memberUsername,
      display_name: 'RA 普通成员',
      password: memberPassword,
      role_ids: [memberRole.id],
    },
  })
  expect(createdMember.status()).toBe(200)
  await page.getByRole('main').getByRole('button', { name: '退出登录' }).click()
  await expect(page).toHaveURL(/\/login$/)
  expect(await page.evaluate(() => localStorage.getItem('iterflow.access_token'))).toBeNull()
  expect(await page.evaluate(() => localStorage.getItem('iterflow.refresh_token'))).toBeNull()
  await page.goto('/profile')
  await expect(page).toHaveURL(/\/login\?/)
  expect(new URL(page.url()).searchParams.get('redirect')).toBe('/profile')
  await page.getByPlaceholder('用户名').fill(memberUsername)
  await page.getByPlaceholder('密码').fill(memberPassword)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '修改初始密码' })).toBeVisible()
  await page.locator('input[type="password"]').nth(0).fill(memberPassword)
  await page.locator('input[type="password"]').nth(1).fill(`${memberPassword}-changed`)
  await page.locator('input[type="password"]').nth(2).fill(`${memberPassword}-changed`)
  await page.getByRole('button', { name: '保存新密码' }).click()
  await expect(page.getByRole('heading', { name: '首页 / 系统概览' })).toBeVisible()
  await page.goto('/profile')
  await expect(page.getByRole('heading', { name: '个人中心' })).toBeVisible()
  await expect(page.getByText(memberUsername)).toBeVisible()
  const memberToken = await page.evaluate(() => localStorage.getItem('iterflow.access_token'))
  const memberMe = await page.request.get('/api/v1/auth/me', {
    headers: { Authorization: `Bearer ${memberToken}` },
  })
  expect(memberMe.status()).toBe(200)
  expect((await memberMe.json()).permission_codes).not.toContain('sys.user.edit')
  await page.setViewportSize({ width: 375, height: 900 })
  for (const label of ['首页', '反馈', '需求', '版本', '消息', '我的']) {
    await expect(page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: label })).toBeVisible()
  }
  expect(browserErrors).toEqual([])
})
