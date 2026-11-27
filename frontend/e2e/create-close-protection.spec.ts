import { expect, test, type Page } from '@playwright/test'
import { mockCollaboration } from './collaboration-fixture'

async function fixture(page: Page) {
  const errors: string[] = [], unexpected: string[] = [], writes: string[] = []
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  page.on('pageerror', e => errors.push(e.message))
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'close-protection')
    localStorage.setItem('iterflow.refresh_token', 'close-protection')
  })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    const reply = (json: unknown, status = 200) => route.fulfill({ json, status })
    if (route.request().method() === 'POST') {
      writes.push(path)
      await gate
      return reply({ message: '合成提交失败，保留草稿' }, 503)
    }
    if (await mockCollaboration(route)) return
    if (path === '/api/v1/auth/me') return reply({ id: 1, username: 'close-protection', display_name: '合成验收', status: 'ACTIVE', must_change_password: false, permission_codes: ['*'], data_scope: 'ALL', role_ids: [] })
    if (path === '/api/v1/notifications/unread-count') return reply({ unread_count: 0 })
    if (path === '/api/v1/systems') return reply({ systems: [], modules: [] })
    if (path === '/api/v1/collaboration/people') return reply({ items: [{ id: 1, display_name: '合成接收人' }], total: 1, page: 1, page_size: 20 })
    if (path === '/api/v1/requirements' || path === '/api/v1/feedbacks') return reply({ items: [], total: 0, page: 1, page_size: 20 })
    unexpected.push(path)
    return reply({}, 500)
  })
  return { errors, unexpected, writes, release }
}

for (const kind of ['feedbacks', 'requirements'] as const) {
  const name = kind === 'feedbacks' ? '提交反馈' : '新建需求'
  for (const width of [1440, 375]) test(`${kind} Esc, repeated Esc and explicit close preserve create draft at ${width}px`, async ({ page }, info) => {
    const audit = await fixture(page)
    await page.setViewportSize({ width, height: 900 })
    await page.goto(`/#/${kind}`)
    await page.getByRole('button', { name, exact: true }).click()
    const form = page.getByRole('dialog', { name, exact: true })
    await expect(form).toBeVisible()
    await page.keyboard.press('Escape')
    const clean = page.getByRole('dialog', { name: '确认关闭？', exact: true })
    await expect(clean).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(clean).toBeVisible()
    await clean.getByRole('button', { name: '继续编辑', exact: true }).click()
    await expect(clean).toBeHidden()
    await form.getByRole('textbox', { name: /^\*?标题$/ }).fill('未保存的标题')
    const description = form.getByRole('textbox', { name: kind === 'feedbacks' ? /详细描述$/ : '需求描述', exact: kind === 'requirements' })
    await description.fill('误触退出仍应保留的描述')
    await page.keyboard.press('Escape')
    const dirty = page.getByRole('dialog', { name: '放弃未保存的修改？', exact: true })
    await expect(dirty).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dirty).toBeVisible()
    await expect(page.getByRole('dialog', { name: '放弃未保存的修改？', exact: true })).toHaveCount(1)
    await dirty.getByRole('button', { name: '继续编辑', exact: true }).click()
    await expect(dirty).toBeHidden()
    await expect(form.getByRole('textbox', { name: /^\*?标题$/ })).toHaveValue('未保存的标题')
    await expect(description).toHaveText('误触退出仍应保留的描述')
    await form.getByRole('button', { name: '关闭此对话框', exact: true }).click()
    await expect(dirty).toBeVisible()
    await dirty.getByRole('button', { name: '继续编辑', exact: true }).click()
    await expect(dirty).toBeHidden()
    await form.getByRole('button', { name: '取消', exact: true }).click()
    await expect(dirty).toBeVisible()
    await dirty.getByRole('button', { name: '继续编辑', exact: true }).click({ trial: true })
    await page.screenshot({ path: info.outputPath('close-confirmation.png'), animations: 'disabled' })
    await dirty.getByRole('button', { name: '放弃修改', exact: true }).click()
    await expect(form).toBeHidden()
    await page.getByRole('button', { name, exact: true }).click()
    await expect(form.getByRole('textbox', { name: /^\*?标题$/ })).toHaveValue('')
    expect(audit.writes).toEqual([])
    expect(audit.errors).toEqual([])
    expect(audit.unexpected).toEqual([])
  })

  test(`${kind} blocks Esc while submitting and protects draft after failure`, async ({ page }) => {
    const audit = await fixture(page)
    await page.goto(`/#/${kind}`)
    await page.getByRole('button', { name, exact: true }).click()
    const form = page.getByRole('dialog', { name, exact: true })
    await form.getByRole('textbox', { name: /^\*?标题$/ }).fill('提交中的标题')
    await form.getByRole('textbox', { name: kind === 'feedbacks' ? /详细描述$/ : '需求描述', exact: kind === 'requirements' }).fill('提交中的具体描述')
    if (kind === 'feedbacks') {
      await form.locator('.el-select__wrapper').filter({ has: page.getByRole('combobox', { name: /反馈接收人/ }) }).click()
      await page.getByRole('option', { name: /合成接收人/ }).click()
      await form.getByRole('textbox', { name: /^\*?标题$/ }).click()
    } else {
      const confirmer = form.locator('[data-field="confirm"]')
      await confirmer.locator('.el-select__wrapper').click()
      await page.getByRole('option', { name: '合成接收人', exact: true }).click()
      await confirmer.getByRole('combobox').press('Escape')
    }
    await form.getByRole('button', { name: kind === 'feedbacks' ? '提交' : '创建', exact: true }).click()
    await expect.poll(() => audit.writes.length).toBe(1)
    await page.keyboard.press('Escape')
    await expect(form).toBeVisible()
    await expect(form.getByRole('button', { name: '关闭此对话框', exact: true })).toBeHidden()
    await expect(page.getByRole('dialog', { name: '放弃未保存的修改？', exact: true })).toBeHidden()
    audit.release()
    await expect(form.getByRole('button', { name: kind === 'feedbacks' ? '提交' : '创建', exact: true })).toBeEnabled()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog', { name: '放弃未保存的修改？', exact: true })).toBeVisible()
    expect(audit.writes).toHaveLength(1)
    expect(audit.unexpected).toEqual([])
  })
}

test('feedback staged attachment alone is protected and retained without uploading', async ({ page }) => {
  const audit = await fixture(page)
  await page.goto('/#/feedbacks')
  await page.getByRole('button', { name: '提交反馈', exact: true }).click()
  const form = page.getByRole('dialog', { name: '提交反馈', exact: true })
  await form.locator('.el-upload input[type="file"]').setInputFiles({ name: 'draft.txt', mimeType: 'text/plain', buffer: Buffer.from('draft attachment') })
  await expect(form.getByText('draft.txt', { exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  const prompt = page.getByRole('dialog', { name: '放弃未保存的修改？', exact: true })
  await expect(prompt).toBeVisible()
  await prompt.getByRole('button', { name: '继续编辑', exact: true }).click()
  await expect(prompt).toBeHidden()
  await expect(form.getByText('draft.txt', { exact: true })).toBeVisible()
  expect(audit.writes).toEqual([])
  expect(audit.errors).toEqual([])
  expect(audit.unexpected).toEqual([])
})
