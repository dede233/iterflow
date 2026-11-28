import { expect, test, type Page } from '@playwright/test'
import type { components } from '../src/types/openapi.generated'
import { mockCollaboration } from './collaboration-fixture'

type Preference = components['schemas']['WecomPreferencesOut']
type PreferenceChange = components['schemas']['WecomPreferenceChange']
type BindingChange = components['schemas']['WecomBindingChange']
type Operator = components['schemas']['AuthMe']

const administrator: Operator = {
  id: 1, username: 'admin', display_name: '超级管理员', email: null, status: 'ACTIVE',
  revision: 1, must_change_password: false, data_scope: 'ALL', role_ids: [1], permission_codes: ['*'],
}
const member: Operator = {
  ...administrator, id: 20, username: 'test-member', display_name: '测试成员',
  data_scope: 'SELF', role_ids: [], permission_codes: [],
}

async function mockWecom(page: Page, operator: Operator, enabled = true) {
  let preference: Preference = { revision: 0, mode: 'OFF', member_user_id: null, enabled }
  let bindingReads = 0
  const bindingWrites: BindingChange[] = []
  const preferenceWrites: PreferenceChange[] = []
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'wecom-test-access')
    localStorage.setItem('iterflow.refresh_token', 'wecom-test-refresh')
  })
  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const method = request.method()
    const { pathname } = new URL(request.url())
    const json = (body: unknown) => route.fulfill({ json: body })
    const conflict = (code: number, message: string) => route.fulfill({ status: 409, json: { code, message } })
    switch (pathname) {
      case '/api/v1/auth/me':
        return json(operator)
      case '/api/v1/notifications/unread-count':
        return json({ unread_count: 0 })
      case '/api/v1/me/mail-preferences':
        return json({ revision: 1, mode: 'TASKS', email: null, verified: false, pending_email: null, smtp_enabled: false, notice_acknowledged: true })
      case '/api/v1/roles':
        return json([{ id: 1, code: 'SUPER_ADMIN', name: '超级管理员', enabled: true, is_system: true }])
      case '/api/v1/users':
        return json({ items: [{ ...member, email_verification_status: 'NO_EMAIL' }], total: 1, page: 1, page_size: 20 })
      case '/api/v1/users/20/wecom-binding': {
        if (method === 'GET') {
          bindingReads++
          return json(preference)
        }
        expect(method).toBe('PUT')
        const change: BindingChange = request.postDataJSON()
        bindingWrites.push(change)
        if (change.revision !== preference.revision) return conflict(40910, '已变更')
        if (change.member_user_id === 'unavailable-userid') return conflict(40901, '该企业微信成员无法绑定')
        preference = { ...preference, member_user_id: change.member_user_id, revision: change.revision + 1, mode: 'OFF' }
        return json(preference)
      }
      case '/api/v1/me/wecom-preferences': {
        if (method === 'GET') return json(preference)
        expect(method).toBe('PUT')
        const change: PreferenceChange = request.postDataJSON()
        preferenceWrites.push(change)
        if (change.revision !== preference.revision) return conflict(40910, '已变更')
        if (!preference.member_user_id && change.mode !== 'OFF') return conflict(40901, '请先由超级管理员绑定企业微信成员')
        preference = { ...preference, mode: change.mode, revision: change.revision + 1 }
        return json(preference)
      }
    }
    if (await mockCollaboration(route)) return
    throw new Error(`Unexpected API request: ${method} ${pathname}`)
  })
  return {
    bindingReads: () => bindingReads,
    bindingWrites,
    preferenceWrites,
    update(next: Partial<Preference>) {
      preference = { ...preference, ...next, revision: preference.revision + 1 }
    },
  }
}

for (const width of [375, 1440]) {
  test(`hides disabled WeCom settings and bindings at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 820 })
    const server = await mockWecom(page, administrator, false)
    server.update({ member_user_id: 'member.test', mode: 'TASKS' })

    await Promise.all([
      page.waitForResponse('**/api/v1/me/wecom-preferences'),
      page.goto('/#/profile'),
    ])
    await expect(page.getByRole('heading', { name: '邮件通知', exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: '企业微信通知', exact: true })).toHaveCount(0)

    await Promise.all([
      page.waitForResponse('**/api/v1/me/wecom-preferences'),
      page.goto('/#/system/users'),
    ])
    const edit = page.getByRole('button', { name: '编辑', exact: true })
    await expect(edit).toBeVisible()
    await expect(page.getByRole('button', { name: '企业微信绑定', exact: true })).toHaveCount(0)
    if (width === 375) expect((await edit.boundingBox())?.height).toBeGreaterThanOrEqual(44)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    expect(server.bindingReads()).toBe(0)
  })

  test(`administrator can bind and unbind a member with revision protection at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 820 })
    const server = await mockWecom(page, administrator)
    await page.goto('/#/system/users')
    const open = page.getByRole('button', { name: '企业微信绑定', exact: true })
    await expect(open).toBeVisible()
    expect(server.bindingReads()).toBe(0)
    if (width === 375) expect((await open.boundingBox())?.height).toBeGreaterThanOrEqual(44)
    await open.click()
    const dialog = page.getByRole('dialog', { name: '企业微信成员绑定' })
    const field = dialog.getByRole('textbox', { name: '企业微信成员账号（UserID）' })
    const save = dialog.getByRole('button', { name: '保存绑定', exact: true })
    await expect(field).toBeEnabled()
    await expect(dialog.getByText('未绑定', { exact: true })).toBeVisible()
    await field.fill('invalid user id')
    await expect(save).toBeDisabled()
    expect(server.bindingWrites).toEqual([])

    server.update({ member_user_id: 'other-session', mode: 'TASKS' })
    await field.fill('unavailable-userid')
    await save.click()
    await expect(dialog.getByRole('alert')).toContainText('输入会保留')
    await expect(save).toBeDisabled()
    await dialog.getByRole('button', { name: '刷新绑定' }).click()
    await expect(dialog.getByText('other-session', { exact: true })).toBeVisible()
    await expect(field).toHaveValue('unavailable-userid')
    expect(server.bindingWrites).toEqual([{ revision: 0, member_user_id: 'unavailable-userid' }])
    await save.click()
    await expect(dialog.getByRole('alert')).toContainText('无法保存成员绑定')
    await expect(field).toHaveValue('unavailable-userid')

    await field.fill(' member.test ')
    const bounds = await dialog.boundingBox()
    expect(bounds!.x).toBeGreaterThanOrEqual(0)
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width)
    await page.screenshot({ path: testInfo.outputPath(`wecom-binding-${width}.png`), animations: 'disabled' })
    await save.click()
    await expect(dialog).toBeHidden()
    await expect(page.getByText('企业微信成员绑定已保存。')).toBeVisible()
    expect(server.bindingWrites).toEqual([
      { revision: 0, member_user_id: 'unavailable-userid' },
      { revision: 1, member_user_id: 'unavailable-userid' },
      { revision: 1, member_user_id: 'member.test' },
    ])

    await open.click()
    await expect(field).toHaveValue('member.test')
    await field.clear()
    await dialog.getByRole('button', { name: '解除绑定', exact: true }).click()
    await expect(page.getByText('企业微信成员绑定已解除。')).toBeVisible()
    expect(server.bindingWrites.at(-1)).toEqual({ revision: 2, member_user_id: null })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
  })

  test(`a bound member can save enabled notification preferences at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 820 })
    const server = await mockWecom(page, member)
    await page.goto('/#/profile')
    const panel = page.locator('.section-card').filter({ has: page.getByRole('heading', { name: '企业微信通知', exact: true }) })
    const choice = panel.getByRole('combobox', { name: '接收范围' })
    const save = panel.getByRole('button', { name: '保存企业微信偏好', exact: true })
    await expect(panel.getByText('未绑定', { exact: true })).toBeVisible()
    await expect(panel.getByText('关闭', { exact: true })).toBeVisible()
    await expect(choice).toBeDisabled()
    await expect(save).toBeDisabled()

    server.update({ member_user_id: 'member.test' })
    await page.reload()
    await expect(panel.getByText('已绑定', { exact: true })).toBeVisible()
    await panel.locator('.el-select__wrapper').click()
    await page.getByRole('option', { name: '仅待办与上线', exact: true }).click()
    server.update({ mode: 'ALL' })
    await save.click()
    await expect(panel.getByRole('alert')).toContainText('所选偏好会保留')
    await expect(save).toBeDisabled()
    await panel.getByRole('button', { name: '刷新设置' }).click()
    await expect(panel.getByText('已保存的偏好为「全部关键通知」。')).toBeVisible()
    await expect(panel.getByText('仅待办与上线', { exact: true })).toBeVisible()
    expect(server.preferenceWrites).toEqual([{ revision: 1, mode: 'TASKS' }])
    await save.click()
    await expect(panel.getByText('企业微信通知偏好已保存。')).toBeVisible()
    expect(server.preferenceWrites).toEqual([{ revision: 1, mode: 'TASKS' }, { revision: 2, mode: 'TASKS' }])
    await page.reload()
    await expect(panel.getByText('仅待办与上线', { exact: true })).toBeVisible()
    await panel.scrollIntoViewIfNeeded()
    await page.screenshot({ path: testInfo.outputPath(`wecom-preference-${width}.png`), animations: 'disabled' })
    await panel.locator('.el-select__wrapper').click()
    await page.getByRole('option', { name: '关闭', exact: true }).click()
    await save.click()
    await expect(panel.getByText('企业微信通知偏好已保存。')).toBeVisible()
    expect(server.preferenceWrites.at(-1)).toEqual({ revision: 3, mode: 'OFF' })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
  })
}

test('editing users alone does not grant access to WeCom bindings', async ({ page }) => {
  const server = await mockWecom(page, { ...administrator, role_ids: [] })
  await page.goto('/#/system/users')
  await expect(page.getByRole('button', { name: '编辑', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '企业微信绑定', exact: true })).toHaveCount(0)
  expect(server.bindingReads()).toBe(0)
  expect(server.bindingWrites).toEqual([])
})
