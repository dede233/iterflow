import { expect, test, type APIResponse } from '@playwright/test'

type Resource = { id: number; revision: number; status: string }
type Role = { id: number; code: string }
type User = { id: number; revision: number }
type Notification = {
  id: number
  title: string
  entity_type: string | null
  entity_id: number | null
  read_at: string | null
}

async function ok<T>(response: APIResponse): Promise<T> {
  expect(response.status(), await response.text()).toBe(200)
  return response.json() as Promise<T>
}

test('real publish notification opens the submitter feedback and respects the router permission guard', async ({ page }) => {
  const adminUsername = process.env.INIT_ADMIN_USERNAME
  const adminPassword = process.env.ITERFLOW_BROWSER_NEW_PASSWORD
  if (!adminUsername || !adminPassword) throw new Error('Fresh acceptance administrator credentials are required')

  const browserErrors: string[] = []
  page.on('pageerror', (error) => browserErrors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text())
  })

  const adminSession = await ok<{ access_token: string }>(await page.request.post('/api/v1/auth/login', {
    data: { username: adminUsername, password: adminPassword },
  }))
  const adminHeaders = { Authorization: `Bearer ${adminSession.access_token}` }
  const roles = await ok<Role[]>(await page.request.get('/api/v1/roles', { headers: adminHeaders }))
  const memberRole = roles.find((role) => role.code === 'MEMBER')
  expect(memberRole).toBeTruthy()

  const suffix = Date.now().toString(36)
  const memberUsername = `ra-notify-${suffix}`
  const initialPassword = `Member!${suffix}Initial`
  const changedPassword = `Member!${suffix}Changed`
  const member = await ok<User>(await page.request.post('/api/v1/users', {
    headers: adminHeaders,
    data: {
      username: memberUsername,
      display_name: '发布通知验收成员',
      password: initialPassword,
      role_ids: [memberRole!.id],
    },
  }))

  // Authenticate the real submitter in the browser, including the required first password change.
  await page.goto('/login')
  await page.getByPlaceholder('用户名').fill(memberUsername)
  await page.getByPlaceholder('密码').fill(initialPassword)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '修改初始密码' })).toBeVisible()
  await page.locator('input[type="password"]').nth(0).fill(initialPassword)
  await page.locator('input[type="password"]').nth(1).fill(changedPassword)
  await page.locator('input[type="password"]').nth(2).fill(changedPassword)
  await page.getByRole('button', { name: '保存新密码' }).click()
  await expect(page.getByRole('heading', { name: '首页 / 系统概览' })).toBeVisible()
  const memberToken = await page.evaluate(() => localStorage.getItem('iterflow.access_token'))
  expect(memberToken).toBeTruthy()
  const memberHeaders = { Authorization: `Bearer ${memberToken}` }

  const feedback = await ok<Resource & { feedback_no: string }>(await page.request.post('/api/v1/feedbacks', {
    headers: memberHeaders,
    data: { title: `真实发布通知反馈-${suffix}`, feedback_type: 'NEW_FEATURE', description: '真实发布通知跳转验收' },
  }))
  const accepted = await ok<Resource>(await page.request.patch(`/api/v1/feedbacks/${feedback.id}/status`, {
    headers: adminHeaders,
    data: { status: 'ACCEPTED', revision: feedback.revision },
  }))
  const requirement = await ok<Resource>(await page.request.post(`/api/v1/feedbacks/${feedback.id}/convert`, {
    headers: adminHeaders,
    data: {
      type: 'CREATE_NEW', revision: accepted.revision,
      requirement_title: `真实发布通知需求-${suffix}`,
      requirement_type: 'FEATURE', priority: 'P2', description: '真实发布链需求',
    },
  }))
  let version = await ok<Resource>(await page.request.post('/api/v1/versions', {
    headers: adminHeaders,
    data: { version_no: `RA-NOTIFY-${suffix}`, name: '真实发布通知验收版本' },
  }))
  version = await ok<Resource>(await page.request.post(`/api/v1/versions/${version.id}/requirements`, {
    headers: adminHeaders,
    data: { requirement_id: requirement.id, revision: requirement.revision, version_revision: version.revision },
  }))
  let currentRequirement = await ok<Resource>(await page.request.get(`/api/v1/requirements/${requirement.id}`, {
    headers: adminHeaders,
  }))
  for (const status of ['DEVELOPING', 'TESTING', 'DONE']) {
    currentRequirement = await ok<Resource>(await page.request.patch(`/api/v1/requirements/${requirement.id}/status`, {
      headers: adminHeaders,
      data: { status, revision: currentRequirement.revision },
    }))
  }
  for (const status of ['DEVELOPING', 'TESTING', 'READY']) {
    version = await ok<Resource>(await page.request.patch(`/api/v1/versions/${version.id}/status`, {
      headers: adminHeaders,
      data: { status, revision: version.revision },
    }))
  }
  const publishCheck = await ok<{ passed: boolean }>(await page.request.post(`/api/v1/versions/${version.id}/publish/check`, {
    headers: adminHeaders,
  }))
  expect(publishCheck.passed).toBe(true)
  const published = await ok<{ release: { result: string }; online_feedback_ids: number[] }>(
    await page.request.post(`/api/v1/versions/${version.id}/publish`, {
      headers: adminHeaders,
      data: { released_at: new Date().toISOString(), release_notes: '正式发布通知浏览器验收', revision: version.revision },
    }),
  )
  expect(published.release.result).toBe('SUCCESS')
  expect(published.online_feedback_ids).toContain(feedback.id)

  const notifications = await ok<Notification[]>(await page.request.get('/api/v1/notifications', {
    headers: memberHeaders,
  }))
  const publishedNotification = notifications.find((item) => item.entity_type === 'FEEDBACK' && item.entity_id === feedback.id)
  expect(publishedNotification).toBeTruthy()
  expect(publishedNotification!.read_at).toBeNull()
  expect(publishedNotification!.title).toContain('已上线')

  await page.goto('/notifications')
  const readResponse = page.waitForResponse((response) =>
    response.url().endsWith(`/api/v1/notifications/${publishedNotification!.id}/read`)
    && response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: new RegExp(publishedNotification!.title) }).click()
  expect((await readResponse).status()).toBe(200)
  await expect(page).toHaveURL(new RegExp(`/feedbacks/${feedback.id}$`))
  await expect(page.getByRole('heading', { name: `真实发布通知反馈-${suffix}` })).toBeVisible()
  const finalFeedback = await ok<Resource>(await page.request.get(`/api/v1/feedbacks/${feedback.id}`, {
    headers: memberHeaders,
  }))
  expect(finalFeedback.status).toBe('ONLINE')
  const readNotifications = await ok<Notification[]>(await page.request.get('/api/v1/notifications', {
    headers: memberHeaders,
  }))
  expect(readNotifications.find((item) => item.id === publishedNotification!.id)?.read_at).not.toBeNull()

  // The notification does not grant cross-domain access: remove the role, refresh AuthMe, and retry.
  const latestMember = await ok<User>(await page.request.get(`/api/v1/users/${member.id}`, { headers: adminHeaders }))
  await ok<User>(await page.request.put(`/api/v1/users/${member.id}/roles`, {
    headers: adminHeaders,
    data: { role_ids: [], revision: latestMember.revision },
  }))
  await page.goto('/notifications')
  await expect(page.getByRole('button', { name: new RegExp(publishedNotification!.title) })).toBeVisible()
  await page.getByRole('button', { name: new RegExp(publishedNotification!.title) }).click()
  await expect(page).toHaveURL(/\/forbidden$/)
  expect(browserErrors).toEqual([])
})
