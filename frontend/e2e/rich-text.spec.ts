import { expect, test, type Page } from '@playwright/test'

async function setup(page: Page, description = '<img src=x onerror="window.richAttack=1">旧文本', format = 'PLAIN', confirmed = false) {
  const requirement = { id: 1, requirement_no: 'REQ-RICH', title: '富文本需求', requirement_type: 'FEATURE', source: 'DIRECT', priority: 'P2', status: confirmed ? 'CONFIRMED' : 'DRAFT', system_id: null, module_id: null, owner_id: null, current_version_id: null, description, description_format: format, acceptance_criteria: '保持旧文本语义', revision: 4, created_at: '2026-11-04T00:00:00Z', updated_at: '2026-11-04T00:00:00Z', updated_by: 1 }
  let contentRevision = 1
  const confirmedRevision = confirmed ? 1 : null
  const feedback = { id: 1, feedback_no: 'FB-RICH', title: '富文本反馈转需求', feedback_type: 'BUG', urgency: 'NORMAL', status: 'NEW', description, system_id: null, module_id: null, submitter_id: 1, main_requirement_id: null, duplicate_of_id: null, handler_id: null, revision: 4, created_at: requirement.created_at, updated_at: requirement.updated_at }
  const writes: { path: string; method: string; body: any }[] = [], unexpected: string[] = [], errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => { localStorage.setItem('iterflow.access_token', 'rich-local'); localStorage.setItem('iterflow.refresh_token', 'rich-local') })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname, method = route.request().method()
    const json = (value: unknown) => route.fulfill({ json: value })
    if (method === 'POST' && path.startsWith('/api/v1/editing/')) return json({ existing_editor: null, ok: true })
    if ((method === 'POST' && path === '/api/v1/requirements') || (method === 'PATCH' && path === '/api/v1/requirements/1') || (method === 'POST' && path === '/api/v1/feedbacks/1/convert')) {
      const body = route.request().postDataJSON()
      writes.push({ path, method, body })
      if (method === 'PATCH' && (body.description !== requirement.description || body.description_format !== requirement.description_format)) contentRevision++
      Object.assign(requirement, body, { title: body.requirement_title || body.title || requirement.title, revision: requirement.revision + 1 })
      return json(requirement)
    }
    const responses: Record<string, unknown> = {
      '/api/v1/auth/me': { id: 1, username: 'rich-local', display_name: '本地合成账号', status: 'ACTIVE', must_change_password: false, permission_codes: ['*'], can_view_api_docs: true, data_scope: 'ALL', role_ids: [], revision: 1 },
      '/api/v1/me/mail-preferences': { revision: 1, mode: 'TASKS', email: null, pending_email: null, verified: false, smtp_enabled: false, notice_acknowledged: true },
      '/api/v1/notifications/unread-count': { unread_count: 0 }, '/api/v1/systems': { systems: [], modules: [] },
      '/api/v1/requirements/1': requirement,
      '/api/v1/requirements/1/workflow': { revision: requirement.revision, content_revision: contentRevision, confirmed_revision: confirmedRevision, needs_confirmation: confirmedRevision !== contentRevision, legacy_completed: false, design_status: 'NOT_REQUIRED', paused_from: null, records: [] },
      '/api/v1/requirements/1/participants': { revision: requirement.revision, participants: (confirmed ? ['CONFIRM', 'DEVELOP'] : ['CONFIRM']).map(role => ({ user_id: 1, role, display_name: '本地合成账号', active: true })) },
      '/api/v1/requirements/1/feedbacks': [],
      '/api/v1/collaboration/people': { items: [{ id: 1, display_name: '本地合成账号' }], total: 1, page: 1, page_size: 20 },
      '/api/v1/feedbacks/1': feedback, '/api/v1/feedbacks/1/attachments': [], '/api/v1/feedbacks/1/comments': [],
      '/api/v1/feedbacks/1/collaboration': { revision: feedback.revision, recipients: [{ id: 1, display_name: '本地合成账号' }], handler_id: null, accepted_by: null, accepted_at: null },
      '/api/v1/versions/7': { id: 7, version_no: 'VER-RICH', name: '富文本摘要验收', status: 'PLANNING', revision: 1, created_at: requirement.created_at, updated_at: requirement.updated_at },
      '/api/v1/versions/7/requirements': { version_id: 7, items: [requirement], stats: { total: 1, completed: 0, completion_rate: 0, by_status: { DRAFT: 1 } } },
      '/api/v1/releases': { items: [], total: 0, page: 1, page_size: 20 },
    }
    if (method === 'GET' && path in responses) return json(responses[path])
    unexpected.push(`${method} ${path}`)
    return route.fulfill({ status: 500, json: { message: 'Unexpected synthetic request' } })
  })
  return { writes, unexpected, errors, requirement }
}
const clean = (audit: Awaited<ReturnType<typeof setup>>) => { expect(audit.errors).toEqual([]); expect(audit.unexpected).toEqual([]) }
async function noOverflow(page: Page, width: number) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
}

for (const width of [375, 1440]) {
  test(`rich text create toolbar and HTML request at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await setup(page)
    await page.goto('/#/requirements/new')
    await page.getByRole('textbox', { name: /标题/ }).fill('新建格式需求')
    const editor = page.getByRole('textbox', { name: '需求描述', exact: true })
    await editor.fill('重要需求说明'); await editor.press('ControlOrMeta+A')
    await page.getByRole('button', { name: '加粗', exact: true }).click()
    await expect(editor.locator('strong')).toHaveText('重要需求说明')
    await page.getByRole('button', { name: '链接', exact: true }).click()
    await page.getByLabel('链接地址', { exact: true }).fill('https://example.test/docs')
    await page.getByRole('button', { name: '应用链接', exact: true }).click()
    await expect(editor.locator('a')).toHaveAttribute('href', 'https://example.test/docs')
    await noOverflow(page, width)
    await page.locator('.rich-text-editor').evaluate(element => element.scrollIntoView({ block: 'center' }))
    await page.screenshot({ path: info.outputPath('create-rich-text.png'), animations: 'disabled' })
    await page.getByRole('button', { name: '创建', exact: true }).click()
    await expect.poll(() => audit.writes.length).toBe(1)
    expect(audit.writes[0].body.description_format).toBe('HTML')
    expect(audit.writes[0].body.description).toContain('<strong>')
    expect(audit.writes[0].body.description).toContain('https://example.test/docs')
    await expect(page.getByRole('heading', { name: '新建格式需求', exact: true })).toBeVisible()
    clean(audit)
  })

  test(`legacy text remains literal and edits to formatted HTML at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await setup(page)
    await page.goto('/#/requirements/1')
    await expect(page.locator('.rich-text-content.plain')).toHaveText(audit.requirement.description)
    expect(await page.locator('.rich-text-content img').count()).toBe(0)
    await page.getByRole('button', { name: '编辑', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '编辑需求', exact: true })
    const editor = dialog.getByRole('textbox', { name: '需求描述', exact: true })
    await expect(editor).toHaveText(audit.requirement.description)
    expect(await editor.locator('img').count()).toBe(0)
    await editor.fill('新的列表项'); await editor.press('ControlOrMeta+A')
    await dialog.getByRole('button', { name: '无序列表', exact: true }).click()
    await expect(editor.locator('ul li')).toHaveText('新的列表项')
    await noOverflow(page, width)
    await dialog.getByRole('button', { name: '保存', exact: true }).click()
    await expect(dialog).toBeHidden()
    expect(audit.writes).toHaveLength(1)
    expect(audit.writes[0].body).toMatchObject({ description_format: 'HTML', revision: 4 })
    expect(audit.writes[0].body.description).toContain('<ul>')
    expect(await page.evaluate(() => (window as any).richAttack)).toBeUndefined()
    clean(audit)
  })

  test(`confirmed legacy title-only edits preserve PLAIN content and confirmation at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const description = '  旧描述第一行\n<img src=x onerror="window.richAttack=1">第二行\n  '
    const audit = await setup(page, description, 'PLAIN', true)
    await page.goto('/#/requirements/1')
    await expect(page.getByRole('button', { name: '开始开发', exact: true })).toBeEnabled()
    await page.getByRole('button', { name: '编辑', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '编辑需求', exact: true })
    const editor = dialog.getByRole('textbox', { name: '需求描述', exact: true })
    await expect(editor).toContainText('<img src=x onerror="window.richAttack=1">第二行')
    expect(await editor.locator('img').count()).toBe(0)
    await dialog.getByRole('textbox', { name: '标题', exact: true }).fill('仅修正旧需求标题')
    await dialog.getByRole('button', { name: '保存', exact: true }).click()
    await expect(dialog).toBeHidden()
    expect(audit.writes).toHaveLength(1)
    expect(audit.writes[0]).toMatchObject({ method: 'PATCH', path: '/api/v1/requirements/1', body: { title: '仅修正旧需求标题', description, description_format: 'PLAIN', revision: 4 } })
    await expect(page.getByRole('heading', { name: '仅修正旧需求标题', exact: true })).toBeVisible()
    await expect(page.locator('.rich-text-content.plain')).toHaveText(description)
    await expect(page.getByRole('button', { name: '开始开发', exact: true })).toBeEnabled()
    await expect(page.getByRole('button', { name: '确认当前内容', exact: true })).toHaveCount(0)
    expect(await page.locator('.rich-text-content img').count()).toBe(0)
    expect(await page.evaluate(() => (window as any).richAttack)).toBeUndefined()
    await noOverflow(page, width)
    clean(audit)
  })

  test(`feedback conversion preserves literal source and submits rich heading at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await setup(page)
    await page.goto('/#/feedbacks/1')
    await page.getByRole('button', { name: '转需求', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '转为需求', exact: true })
    const editor = dialog.getByRole('textbox', { name: '需求描述', exact: true })
    await expect(editor).toHaveText(audit.requirement.description)
    expect(await editor.locator('img').count()).toBe(0)
    await editor.fill('转换需求标题'); await editor.press('ControlOrMeta+A')
    await dialog.getByRole('button', { name: '标题', exact: true }).click()
    await expect(editor.locator('h2')).toHaveText('转换需求标题')
    await noOverflow(page, width)
    await dialog.getByRole('button', { name: '确定', exact: true }).click()
    await expect.poll(() => audit.writes.length).toBe(1)
    expect(audit.writes[0].body).toMatchObject({ type: 'CREATE_NEW', description_format: 'HTML', revision: 4, participants: [{ role: 'CONFIRM', user_id: 1 }] })
    expect(audit.writes[0].body.description).toContain('<h2>转换需求标题</h2>')
    clean(audit)
  })

  test(`empty edits stay open without PATCH and can be corrected at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await setup(page)
    await page.goto('/#/requirements/1')
    await page.getByRole('button', { name: '编辑', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '编辑需求', exact: true })
    const title = dialog.getByRole('textbox', { name: '标题', exact: true })
    const editor = dialog.getByRole('textbox', { name: '需求描述', exact: true })
    await title.fill('')
    await dialog.getByRole('button', { name: '保存', exact: true }).click()
    await expect(dialog).toBeVisible()
    await expect(page.getByText('请填写需求标题与描述（至少 2 个字符）', { exact: true }).last()).toBeVisible()
    expect(audit.writes).toHaveLength(0)
    await expect(editor).toHaveText(audit.requirement.description)
    await title.fill('修正后标题')
    await editor.fill('')
    await dialog.getByRole('button', { name: '保存', exact: true }).click()
    await expect(page.getByText('请填写需求标题与描述（至少 2 个字符）', { exact: true }).last()).toBeVisible()
    await expect(dialog).toBeVisible()
    expect(audit.writes).toHaveLength(0)
    await expect(title).toHaveValue('修正后标题')
    await editor.fill('修正后描述')
    await dialog.getByRole('button', { name: '保存', exact: true }).click()
    await expect(dialog).toBeHidden()
    expect(audit.writes).toHaveLength(1)
    expect(audit.writes[0].body).toMatchObject({ title: '修正后标题', description: '<p>修正后描述</p>', description_format: 'HTML', revision: 4 })
    clean(audit)
  })

  test(`summary safely renders HTML without script, resources or unsafe links at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await setup(page, '<h2 onclick="window.richAttack=1">格式标题</h2><p>正常说明<img src=x onerror="window.richAttack=1"></p><a href="javascript:window.richAttack=1">危险链接</a><script>window.richAttack=1</script>', 'HTML')
    await page.goto('/#/versions/7')
    await page.getByText('查看', { exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '需求摘要', exact: true })
    await expect(dialog.getByRole('heading', { name: '格式标题', exact: true })).toBeVisible()
    expect(await dialog.locator('.rich-text-content img, .rich-text-content script, .rich-text-content [onclick]').count()).toBe(0)
    await expect(dialog.getByText('危险链接', { exact: true })).not.toHaveAttribute('href')
    expect(await page.evaluate(() => (window as any).richAttack)).toBeUndefined()
    await noOverflow(page, width)
    await page.screenshot({ path: info.outputPath('summary-safe-html.png'), animations: 'disabled' })
    clean(audit)
  })

  test(`invisible format controls cannot submit an empty description at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await setup(page)
    await page.goto('/#/requirements/1')
    await page.getByRole('button', { name: '编辑', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '编辑需求', exact: true })
    const editor = dialog.getByRole('textbox', { name: '需求描述', exact: true })
    for (const value of ['\u2060\u2060', '\u200c\u200d', '\u202a\u202e', ' \u2060\n\u200d\t ']) {
      await editor.fill(value)
      await dialog.getByRole('button', { name: '保存', exact: true }).click()
      await expect(page.getByText('请填写需求标题与描述（至少 2 个字符）', { exact: true }).last()).toBeVisible()
      await expect(dialog).toBeVisible()
      expect(audit.writes).toHaveLength(0)
    }
    await editor.fill('研发👩\u200d💻说明')
    await dialog.getByRole('button', { name: '保存', exact: true }).click()
    await expect(dialog).toBeHidden()
    expect(audit.writes).toHaveLength(1)
    expect(audit.writes[0].body.description).toBe('<p>研发👩\u200d💻说明</p>')
    clean(audit)
  })
}

const pixel = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jZQAAAABJRU5ErkJggg=='
for (const width of [375, 1440]) {
  test(`inserts a file and pastes a screenshot, then opens the stored image at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const audit = await setup(page)
    await page.route('**/api/v1/requirements/1/images/*', route => route.fulfill({ contentType: 'image/png', body: Buffer.from(pixel, 'base64') }))
    await page.goto('/#/requirements/1')
    await page.getByRole('button', { name: '编辑', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '编辑需求', exact: true })
    const editor = dialog.getByRole('textbox', { name: '需求描述', exact: true })
    await editor.fill('截图说明')
    const chooser = page.waitForEvent('filechooser')
    await dialog.getByRole('button', { name: '插入图片' }).click()
    await (await chooser).setFiles({ name: 'local.png', mimeType: 'image/png', buffer: Buffer.from(pixel, 'base64') })
    await expect(editor.getByRole('button', { name: '查看大图' })).toHaveCount(1)
    await editor.evaluate((node, b64) => {
      const clipboardData = new DataTransfer()
      clipboardData.items.add(new File([Uint8Array.from(atob(b64), c => c.charCodeAt(0))], 'screenshot.png', {type: 'image/png'}))
      node.dispatchEvent(new ClipboardEvent('paste', { clipboardData, bubbles: true, cancelable: true }))
    }, pixel)
    await expect(editor.getByRole('button', { name: '查看大图' })).toHaveCount(2)
    await dialog.getByRole('button', { name: '保存', exact: true }).click()
    await expect.poll(() => audit.writes.length).toBe(1)
    const body = audit.writes[0].body
    const keys = Object.keys(body.description_images)
    expect(keys).toHaveLength(2)
    for (const key of keys) expect(body.description).toContain(`data-file-id="${key}"`)
    audit.requirement.description = keys.reduce((s, k, i) => s.replace(k, String(30 + i)), body.description)
    await page.reload()
    await page.getByRole('button', { name: '查看大图' }).first().click()
    const viewer = page.getByRole('dialog', { name: '需求图片大图' })
    await expect(viewer).toBeVisible()
    expect(await viewer.locator('img').evaluate(el => el.naturalWidth)).toBe(1)
    await page.keyboard.press('Escape')
    await expect(viewer).toBeHidden()
    await noOverflow(page, width)
    clean(audit)
  })
}
