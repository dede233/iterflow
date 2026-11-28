import { expect, test, type Locator, type Page } from '@playwright/test'
import { mockCollaboration } from './collaboration-fixture'
import type { components } from '../src/types/openapi.generated'

type AdProductionRecord = components['schemas']['AdProductionOut']
type StatusChange = components['schemas']['AdProductionStatusChange']
type LifecycleAction = components['schemas']['EntityDelete']
type Designer = components['schemas']['AdProductionDesignerOption']
const designers: Designer[] = [{ id: 12, display_name: '林设计' }, { id: 13, display_name: '秦设计' }]
const ccUsers: Designer[] = [{ id: 21, display_name: '陈运营' }, { id: 22, display_name: '陆门店' }]
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/aGQAAAAASUVORK5CYII=', 'base64')
const creatorPermissions = ['ops.ad_production.view', 'ops.ad_production.create']
const editorPermissions = ['ops.ad_production.view', 'ops.ad_production.edit']
const merchantCreatorPermissions = ['ops.merchant_ad.view', 'ops.merchant_ad.create']
const merchantEditorPermissions = ['ops.merchant_ad.view', 'ops.merchant_ad.edit']
const record: AdProductionRecord = {
  id: 7,
  kind: 'MATERIAL',
  work_date: '2026-11-26',
  content: '中央公园店海报设计',
  content_format: 'PLAIN',
  issuer: '运营部',
  status: 'IN_PROGRESS',
  created_by: 1,
  created_at: '2026-11-26T01:00:00Z',
  updated_at: '2026-11-26T01:00:00Z',
  revision: 1,
  images: [],
}

test.use({ timezoneId: 'Asia/Shanghai' })

function recordPublisher(dialog: Locator): Locator {
  return dialog.locator('dl > div').filter({ hasText: '需求发布人' }).locator('dd')
}

async function mockAdProduction(page: Page, options: {
  record?: Partial<AdProductionRecord>
  designers?: Designer[]
  designerFailures?: number
  conflictOnStatus?: boolean
  completeOnUpdate?: boolean
  permissions?: string[]
  actor?: Pick<components['schemas']['AuthMe'], 'id' | 'username' | 'display_name' | 'data_scope'>
  notice?: boolean | 'AD_PRODUCTION_MATERIAL' | 'AD_PRODUCTION_MATERIAL_CC' | 'AD_PRODUCTION_MERCHANT_CC'
  blockedRecordIds?: number[]
} = {}) {
  const original = { ...record, ...options.record }
  let item = { ...original }
  let designerFailures = options.designerFailures ?? 0
  let conflictOnStatus = options.conflictOnStatus
  let completeOnUpdate = options.completeOnUpdate
  let deleted = false
  const designerOptions = options.designers ?? []
  const requests: URLSearchParams[] = []
  const designerRequests: URLSearchParams[] = []
  const ccRequests: URLSearchParams[] = []
  const creations: FormData[] = []
  const updates: FormData[] = []
  const statusUpdates: StatusChange[] = []
  const deletions: LifecycleAction[] = []
  const withdrawals: LifecycleAction[] = []
  const detailRequests: number[] = []
  const imageRequests: string[] = []
  let readAt: string | null = null

  function savedRecord(previous: AdProductionRecord, form: FormData): AdProductionRecord {
    const status = form.get('status') as AdProductionRecord['status'] | null
    const receiverId = form.has('receiver_id') ? Number(form.get('receiver_id')) || null : previous.receiver_id
    const completedById = status !== 'COMPLETED' ? null
      : form.has('completed_by_id') ? Number(form.get('completed_by_id')) || null : previous.completed_by_id
    const ccIds: number[] | undefined = form.has('cc_user_ids') ? JSON.parse(String(form.get('cc_user_ids'))) : undefined
    return {
      ...previous,
      kind: (form.get('kind') as AdProductionRecord['kind'] | null) ?? previous.kind,
      title: form.has('title') ? String(form.get('title')) : previous.title,
      due_at: form.has('clear_due_at') ? null : form.has('due_at') ? String(form.get('due_at')) : previous.due_at,
      work_date: form.has('work_date') ? String(form.get('work_date')) : previous.work_date,
      content: String(form.get('content')),
      content_format: form.get('content_format') as AdProductionRecord['content_format'],
      issuer: form.has('issuer') ? String(form.get('issuer')) : previous.issuer,
      status: status ?? 'NOT_STARTED',
      receiver_id: receiverId,
      receiver_display_name: receiverId === previous.receiver_id ? previous.receiver_display_name : designerOptions.find(person => person.id === receiverId)?.display_name,
      completed_by_id: completedById,
      completed_by_display_name: completedById === previous.completed_by_id ? previous.completed_by_display_name : designerOptions.find(person => person.id === completedById)?.display_name,
      cc_users: ccIds ? [...new Map([...(previous.cc_users ?? []), ...ccUsers].map(person => [person.id, person])).values()]
        .filter(person => ccIds.includes(person.id)) : previous.cc_users,
      processing_result: status === 'COMPLETED' ? String(form.get('processing_result') ?? previous.processing_result ?? '') || null : null,
    }
  }

  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'ad-production-ui-test')
    localStorage.setItem('iterflow.refresh_token', 'ad-production-ui-test-refresh')
  })
  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const readForm = () => new Response(request.postDataBuffer(), {
      headers: { 'Content-Type': request.headers()['content-type']! },
    }).formData()
    switch (url.pathname) {
      case '/api/v1/auth/me':
        return route.fulfill({ json: {
          id: 1, username: 'test-admin', display_name: '测试管理员', email: null, revision: 1,
          status: 'ACTIVE', must_change_password: false, data_scope: 'ALL', role_ids: [],
          ...options.actor,
          permission_codes: options.permissions ?? [
            'dashboard.view', 'rd.feedback.view', 'rd.requirement.view', 'rd.version.view', 'rd.release.view',
            ...creatorPermissions, 'ops.ad_production.edit', ...merchantEditorPermissions, 'ops.merchant_ad.create',
          ],
        } })
      case '/api/v1/notifications/unread-count':
        return route.fulfill({ json: { unread_count: options.notice && !readAt ? 1 : 0 } })
      case '/api/v1/notifications':
        return route.fulfill({ json: options.notice ? [{
          id: 1, type: 'SYSTEM', title: options.notice === 'AD_PRODUCTION_MATERIAL' ? '物料制作需求已撤回' : '新的商家广告制作需求', content: '请查看需求详情。',
          entity_type: typeof options.notice === 'string' ? options.notice : 'AD_PRODUCTION',
          entity_id: item.id, read_at: readAt, created_at: record.created_at,
        }] : [] })
      case '/api/v1/notifications/1/read':
        readAt = record.created_at
        return route.fulfill({ json: { success: true } })
      case '/api/v1/ad-productions/designer-options':
        designerRequests.push(url.searchParams)
        if (designerFailures > 0) {
          designerFailures--
          return route.fulfill({ status: 503, json: { code: 50300, message: '暂不可用' } })
        }
        return route.fulfill({ json: designerOptions })
      case '/api/v1/ad-productions/cc-options':
        ccRequests.push(url.searchParams)
        return route.fulfill({ json: ccUsers.filter(person => person.display_name.includes(url.searchParams.get('keyword') ?? '')) })
      case '/api/v1/ad-productions/7/images/40':
      case '/api/v1/ad-productions/7/content-images/41':
        imageRequests.push(url.pathname)
        return route.fulfill({ body: png, contentType: 'image/png' })
      case '/api/v1/ad-productions':
        if (request.method() === 'POST') {
          const form = await readForm()
          creations.push(form)
          const publisher = options.actor?.display_name ?? '测试管理员'
          item = savedRecord({
            ...record, id: 8, created_by: options.actor?.id ?? 1, issuer: publisher, publisher_display_name: publisher,
          }, form)
          return route.fulfill({ status: 201, json: item })
        }
        requests.push(url.searchParams)
        const kind = url.searchParams.get('kind') ?? 'MATERIAL'
        const records = item.kind === original.kind ? [item] : [item, original]
        const items = deleted ? [] : records.filter(record => record.kind === kind)
        return route.fulfill({ json: { items, total: items.length, page: 1, page_size: 20 } })
      case '/api/v1/ad-productions/7':
      case '/api/v1/ad-productions/8':
        if (request.method() === 'DELETE') {
          const action = request.postDataJSON() as LifecycleAction
          deletions.push(action)
          deleted = true
          return route.fulfill({ json: { id: item.id, revision: item.revision + 1, deleted: true } })
        }
        if (request.method() === 'PATCH') {
          const form = await readForm()
          updates.push(form)
          if (completeOnUpdate || Number(form.get('revision')) !== item.revision) {
            if (completeOnUpdate) {
              item = { ...item, status: 'COMPLETED', revision: item.revision + 1 }
              completeOnUpdate = false
            }
            return route.fulfill({ status: 409, json: {
              code: 40910, message: '记录已更新',
              data: { current_revision: item.revision, current_updated_at: item.updated_at, current_updated_by: 1 },
            } })
          }
          item = savedRecord({ ...item, revision: item.revision + 1 }, form)
          return route.fulfill({ json: item })
        }
        const id = Number(url.pathname.split('/').at(-1))
        detailRequests.push(id)
        if (deleted || options.blockedRecordIds?.includes(id)) {
          return route.fulfill({ status: 404, json: { code: 40400, message: '记录不存在' } })
        }
        return route.fulfill({ json: item.id === id ? item : original })
      case '/api/v1/ad-productions/7/withdraw':
        withdrawals.push(request.postDataJSON() as LifecycleAction)
        item = { ...item, status: 'WITHDRAWN', revision: item.revision + 1, can_withdraw: false }
        return route.fulfill({ json: item })
      case '/api/v1/ad-productions/7/status':
      case '/api/v1/ad-productions/8/status': {
        const change = request.postDataJSON() as StatusChange
        statusUpdates.push(change)
        if (conflictOnStatus || change.revision !== item.revision) {
          if (conflictOnStatus) {
            item = { ...item, revision: item.revision + 1, status: item.kind === 'MERCHANT_AD' ? 'IN_PROGRESS' : 'SHIPPING' }
            conflictOnStatus = false
          }
          return route.fulfill({ status: 409, json: {
            code: 40910, message: '记录已更新',
            data: { current_revision: item.revision, current_updated_at: item.updated_at, current_updated_by: 1 },
          } })
        }
        const completedById = change.status !== 'COMPLETED' ? null : change.completed_by_id === undefined
          ? item.completed_by_id : change.completed_by_id || null
        item = {
          ...item,
          revision: item.revision + 1,
          status: change.status,
          completed_by_id: completedById,
          completed_by_display_name: designerOptions.find(person => person.id === completedById)?.display_name,
          processing_result: change.status === 'COMPLETED' ? change.processing_result ?? item.processing_result : null,
        }
        return route.fulfill({ json: item })
      }
    }
    if (await mockCollaboration(route)) return
    throw new Error(`Unexpected API request: ${request.method()} ${url.pathname}`)
  })

  return { requests, designerRequests, ccRequests, creations, updates, statusUpdates, deletions, withdrawals, detailRequests, imageRequests }
}

test('desktop filters use the shared controls and keep open-ended date searches', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const server = await mockAdProduction(page)
  await page.goto('/#/ad-productions')
  await expect(page.getByRole('heading', { name: '物料制作', exact: true })).toBeVisible()
  const filters = page.locator('.list-filters')
  await expect(filters.getByRole('combobox', { name: '状态' })).toBeVisible()
  await filters.getByTestId('ad-production-filter-status').locator('.el-select__wrapper').click()
  await page.getByRole('option', { name: '进行中', exact: true }).click()
  const startDate = filters.getByRole('combobox', { name: '发布起始日期' })
  await startDate.fill('2026-11-25')
  await startDate.press('Tab')
  await filters.getByRole('button', { name: '查询' }).click()
  await expect.poll(() => server.requests.at(-1)?.get('published_from')).toBe('2026-11-24T16:00:00.000Z')
  expect(server.requests.at(-1)?.get('published_before')).toBeNull()
  expect(server.requests.at(-1)?.get('date_from')).toBeNull()
  expect(server.requests.at(-1)?.get('status')).toBe('IN_PROGRESS')
  const endDate = filters.getByRole('combobox', { name: '发布结束日期' })
  await endDate.fill('2026-11-26')
  await endDate.press('Tab')
  await filters.getByRole('button', { name: '查询' }).click()
  await expect.poll(() => server.requests.at(-1)?.get('published_before')).toBe('2026-11-26T16:00:00.000Z')
  await expect(page.locator('.el-loading-mask:visible')).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath('ad-list-desktop.png'), animations: 'disabled' })

  await page.getByTestId('ad-production-view-7').click()
  const detail = page.getByRole('dialog', { name: '物料制作详情' })
  await expect(detail).toHaveClass(/el-drawer/)
  await expect(detail.getByRole('heading', { name: record.content })).toBeVisible()
  await expect(detail.locator('[datetime="2026-11-26T01:00:00Z"]')).toHaveText(/09:00/)
  await expect(recordPublisher(detail)).toHaveText('用户 #1')
  await expect(page.getByText('下发人', { exact: true })).toHaveCount(0)
  await expect(page.getByText(record.issuer, { exact: true })).toHaveCount(0)
})

for (const scenario of [
  { kind: 'MATERIAL', name: '物料制作', path: '/ad-productions', width: 1440, permissions: creatorPermissions },
  { kind: 'MERCHANT_AD', name: '商家广告', path: '/merchant-ads', width: 375, permissions: merchantCreatorPermissions },
] as const) {
  test(`${scenario.kind} creator deletes eligible records from More`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: scenario.width, height: 900 })
    const server = await mockAdProduction(page, {
      record: { kind: scenario.kind, status: 'NOT_STARTED', can_delete: true },
      permissions: scenario.permissions,
    })
    await page.goto(`/#${scenario.path}?record_id=7`)
    const detail = page.getByRole('dialog', { name: `${scenario.name}详情` })
    const more = detail.getByRole('button', { name: '更多', exact: true })
    await expect(more).toBeVisible()
    if (scenario.width === 375) expect((await more.boundingBox())?.height).toBeGreaterThanOrEqual(44)
    await more.click()
    await page.getByRole('menuitem', { name: '删除', exact: true }).click()
    const confirmation = page.getByRole('dialog', { name: '确认删除' })
    await confirmation.getByRole('button', { name: '确认删除' }).click()
    await expect(confirmation.getByRole('alert')).toHaveText(/至少 2 个字符/)
    expect(server.deletions).toEqual([])
    await confirmation.getByRole('textbox', { name: '删除原因' }).fill('重复发布')
    await expect(confirmation.getByRole('alert')).toHaveCount(0)
    const confirm = confirmation.getByRole('button', { name: '确认删除' })
    if (scenario.width === 375) expect((await confirm.boundingBox())?.height).toBeGreaterThanOrEqual(44)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(scenario.width)
    await page.screenshot({ path: testInfo.outputPath('delete-confirmation.png'), animations: 'disabled' })
    await confirm.click()
    await expect(confirmation).toBeHidden()
    await expect(detail).toBeHidden()
    await expect(page).not.toHaveURL(/record_id=/)
    await expect(page.getByText(`暂无${scenario.name}记录`)).toBeVisible()
    expect(server.deletions).toEqual([{ revision: 1, reason: '重复发布' }])
  })
}

test('merchant creator withdraws from More and the record becomes read-only', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const server = await mockAdProduction(page, {
    record: { kind: 'MERCHANT_AD', status: 'IN_PROGRESS', can_withdraw: true },
    permissions: [...merchantCreatorPermissions, 'ops.merchant_ad.edit'],
  })
  await page.goto('/#/merchant-ads?record_id=7')
  const detail = page.getByRole('dialog', { name: '商家广告详情' })
  await detail.getByRole('button', { name: '更改状态' }).click()
  const editor = page.getByRole('dialog', { name: '更改状态' })
  await editor.getByTestId('ad-production-status').locator('.el-select__wrapper').click()
  await expect(page.getByRole('option', { name: '已处理', exact: true })).toBeVisible()
  await expect(page.getByRole('option', { name: '已撤回', exact: true })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await editor.getByRole('button', { name: '取消', exact: true }).click()

  await detail.getByRole('button', { name: '更多', exact: true }).click()
  await expect(page.getByRole('menuitem', { name: '删除', exact: true })).toHaveCount(0)
  await page.getByRole('menuitem', { name: '撤回', exact: true }).click()
  const confirmation = page.getByRole('dialog', { name: '确认撤回' })
  await confirmation.getByRole('textbox', { name: '撤回原因' }).fill('使用新设计')
  await confirmation.getByRole('button', { name: '确认撤回' }).click()
  await expect(confirmation).toBeHidden()
  await expect(detail.getByText('已撤回', { exact: true })).toBeVisible()
  await expect(detail.getByRole('button', { name: '更多', exact: true })).toHaveCount(0)
  await expect(detail.getByTestId('ad-production-detail-edit')).toHaveCount(0)
  await expect(detail.getByTestId('ad-production-change-status')).toHaveCount(0)
  expect(server.withdrawals).toEqual([{ revision: 1, reason: '使用新设计' }])
  expect(server.statusUpdates).toEqual([])
  await page.screenshot({ path: testInfo.outputPath('withdrawn-mobile-detail.png'), animations: 'disabled' })
  await detail.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page.getByTestId('ad-production-card-7')).toContainText('已撤回')
})

test('material withdrawal notice opens the matching read-only detail', async ({ page }) => {
  await mockAdProduction(page, {
    record: { receiver_id: 12, status: 'WITHDRAWN' },
    actor: { id: 12, username: 'designer', display_name: '林设计', data_scope: 'SELF' },
    permissions: editorPermissions,
    notice: 'AD_PRODUCTION_MATERIAL',
  })
  await page.goto('/#/notifications')
  await page.getByRole('button', { name: /物料制作需求已撤回/ }).click()
  await expect(page).toHaveURL(/#\/ad-productions\?record_id=7$/)
  const detail = page.getByRole('dialog', { name: '物料制作详情' })
  await expect(detail.getByText('已撤回', { exact: true })).toBeVisible()
  await expect(detail.getByRole('button', { name: '更多', exact: true })).toHaveCount(0)
  await expect(detail.getByTestId('ad-production-change-status')).toHaveCount(0)
})

test('a creator publishes a title, content, local deadline and one receiver', async ({ page }) => {
  const server = await mockAdProduction(page, { permissions: creatorPermissions, designers, record: { created_by: 11 } })
  await page.goto('/#/')
  await expect(page).toHaveURL(/#\/ad-productions$/)
  const navigation = page.getByRole('complementary', { name: '侧边导航' })
  await expect(navigation.getByRole('link', { name: '物料制作', exact: true })).toBeVisible()
  await expect(navigation.getByRole('link', { name: '商家广告', exact: true })).toHaveCount(0)
  await expect(page.getByTestId('ad-production-view-7')).toBeVisible()
  await expect(page.getByTestId('ad-production-edit-7')).toHaveCount(0)
  await page.getByRole('button', { name: '发布物料制作需求', exact: true }).click()
  const editor = page.getByRole('dialog', { name: '发布物料制作需求' })
  await expect(editor.getByText(/^(下发人|需求发布人)$/)).toHaveCount(0)
  await expect(editor.getByRole('combobox', { name: '状态' })).toHaveCount(0)
  await expect(editor.getByRole('combobox', { name: '实际完成人' })).toHaveCount(0)
  await page.keyboard.press('Escape')
  const close = page.getByRole('dialog', { name: '确认关闭？' })
  await expect(close).toBeVisible()
  await close.getByRole('button', { name: '继续编辑' }).click()
  await expect(close).toBeHidden()
  for (const trigger of ['关闭此对话框', '取消']) {
    await editor.getByRole('button', { name: trigger, exact: true }).click()
    await expect(close).toBeVisible()
    await close.getByRole('button', { name: '继续编辑' }).click()
    await expect(close).toBeHidden()
  }
  const content = editor.getByRole('textbox', { name: '需求内容' })
  await content.fill('新海报物料')
  await editor.getByRole('button', { name: '发布需求', exact: true }).click()
  await expect(editor.getByText('标题须填写 1–200 字')).toBeVisible()
  await expect(editor.getByText('请选择需求接收人')).toBeVisible()
  expect(server.creations).toHaveLength(0)
  await editor.getByRole('textbox', { name: '标题' }).fill('门店节日海报')
  const receiver = editor.getByRole('combobox', { name: '需求接收人' })
  await receiver.fill('林')
  await page.getByRole('option', { name: '林设计', exact: true }).click()
  expect(server.designerRequests.map(query => query.get('kind'))).toEqual(['MATERIAL'])
  const deadline = editor.getByRole('combobox', { name: '截止时间' })
  const controlWidth = (selector: string) => editor.locator(selector).evaluate(element => element.getBoundingClientRect().width)
  expect(await controlWidth('.el-date-editor')).toBeCloseTo(await controlWidth('.el-select:has(#ad-production-receiver_id)'), 0)
  await deadline.fill('2026-11-30 17:30')
  await deadline.press('Tab')
  await content.press('ControlOrMeta+A')
  await editor.getByRole('button', { name: '加粗', exact: true }).click()
  await editor.locator('.rich-text-editor input[type=file]').setInputFiles({
    name: 'poster.png', mimeType: 'image/png',
    buffer: png,
  })
  await editor.getByRole('button', { name: '发布需求', exact: true }).click()
  await expect(editor).toBeHidden()
  await expect(page.getByRole('button', { name: '门店节日海报', exact: true })).toBeVisible()
  expect(server.creations).toHaveLength(1)
  expect(server.creations[0].get('title')).toBe('门店节日海报')
  expect(server.creations[0].get('kind')).toBe('MATERIAL')
  expect(server.creations[0].get('due_at')).toBe('2026-11-30T09:30:00.000Z')
  expect(server.creations[0].getAll('receiver_id')).toEqual(['12'])
  expect(server.creations[0].has('issuer')).toBe(false)
  expect(server.creations[0].has('work_date')).toBe(false)
  expect(server.creations[0].has('status')).toBe(false)
  expect(server.creations[0].has('completed_by_id')).toBe(false)
  expect(server.creations[0].get('content_format')).toBe('HTML')
  expect(server.creations[0].get('content')).toContain('<strong>新海报物料</strong>')
  const inline = server.creations[0].get('content_images') as File
  expect(inline.name).toMatch(/^local-/)
  expect(inline.type).toBe('image/png')
  expect(server.creations[0].has('images')).toBe(false)
  await page.getByTestId('ad-production-view-8').click()
  const detail = page.getByRole('dialog', { name: '物料制作详情' })
  await expect(recordPublisher(detail)).toHaveText('测试管理员')
  await expect(detail.getByText('未开始', { exact: true })).toBeVisible()
  await expect(detail.locator('[datetime="2026-11-30T09:30:00.000Z"]')).toHaveText(/17:30/)
  await expect(detail.getByRole('button', { name: '更改状态' })).toHaveCount(0)
})

test('a material creator corrects their own unstarted request from the desktop list', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const server = await mockAdProduction(page, {
    permissions: creatorPermissions, designers,
    record: { status: 'NOT_STARTED', receiver_id: 12, receiver_display_name: '林设计' },
  })
  await page.goto('/#/ad-productions')
  await page.getByTestId('ad-production-edit-7').click()
  const editor = page.getByRole('dialog', { name: '编辑物料制作需求' })
  await expect(editor.getByTestId('ad-production-status')).toHaveCount(0)
  await expect(editor.getByRole('combobox', { name: '实际完成人' })).toHaveCount(0)
  await expect(editor.getByRole('textbox', { name: '处理结果' })).toHaveCount(0)
  const receiver = editor.getByRole('combobox', { name: '需求接收人' })
  await expect(editor.getByText('林设计', { exact: true })).toBeVisible()
  const receiverControl = editor.locator('.el-select:has(#ad-production-receiver_id)')
  await receiverControl.hover()
  await expect(receiverControl.locator('.el-select__clear')).toHaveCount(0)
  await receiver.fill('秦')
  await page.getByRole('option', { name: '秦设计', exact: true }).click()
  await editor.getByRole('textbox', { name: '标题' }).fill('中央公园店节日海报')
  await editor.getByRole('textbox', { name: '需求内容' }).fill('修正海报尺寸和门店信息。')
  const deadline = editor.getByRole('combobox', { name: '截止时间' })
  await deadline.fill('2026-11-30 17:30')
  await deadline.press('Tab')
  const image = { name: 'poster.png', mimeType: 'image/png', buffer: png }
  await editor.locator('.rich-text-editor input[type=file]').setInputFiles(image)
  await editor.getByTestId('ad-production-images-input').setInputFiles(image)
  await page.screenshot({ path: testInfo.outputPath('author-correction-desktop.png'), animations: 'disabled' })
  await editor.getByTestId('ad-production-save').click()
  await expect(editor).toBeHidden()
  await expect(page.getByRole('button', { name: '中央公园店节日海报', exact: true })).toBeVisible()
  expect(server.updates).toHaveLength(1)
  const [update] = server.updates
  expect(update.get('revision')).toBe('1')
  expect(update.get('status')).toBe('NOT_STARTED')
  expect(update.get('work_date')).toBe(record.work_date)
  expect(update.get('issuer')).toBe(record.issuer)
  expect(update.get('receiver_id')).toBe('13')
  expect(update.get('due_at')).toBe('2026-11-30T09:30:00.000Z')
  expect(update.get('content')).toContain('修正海报尺寸和门店信息。')
  expect(update.get('content_format')).toBe('HTML')
  expect((update.get('content_images') as File).name).toMatch(/^local-/)
  expect((update.get('images') as File).name).toBe('poster.png')
  expect(update.has('completed_by_id')).toBe(false)
  expect(update.has('processing_result')).toBe(false)
  expect(server.statusUpdates).toHaveLength(0)
})

test('a merchant creator corrects an in-progress request from the 375px detail drawer', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const server = await mockAdProduction(page, {
    permissions: merchantCreatorPermissions,
    record: { kind: 'MERCHANT_AD', title: '更新中央公园店二维码', receiver_id: null },
  })
  await page.goto('/#/merchant-ads')
  await page.getByTestId('ad-production-card-7').click()
  const detail = page.getByRole('dialog', { name: '商家广告详情' })
  await expect(detail.getByRole('heading', { name: '更新中央公园店二维码' })).toBeVisible()
  await expect(detail.getByTestId('ad-production-change-status')).toHaveCount(0)
  await detail.getByTestId('ad-production-detail-edit').click()
  const editor = page.getByRole('dialog', { name: '编辑商家广告需求' })
  await expect(editor.getByRole('combobox', { name: '需求接收人' })).toBeDisabled()
  await expect(editor.getByTestId('ad-production-status')).toHaveCount(0)
  await expect(editor.getByRole('combobox', { name: '实际完成人' })).toHaveCount(0)
  await expect(editor.getByRole('textbox', { name: '处理结果' })).toHaveCount(0)
  await editor.getByRole('textbox', { name: '标题' }).fill('更新北门店二维码')
  await editor.locator('.el-select:has(#ad-production-cc-users) .el-select__wrapper').click()
  await editor.getByRole('combobox', { name: '抄送人' }).fill('陈')
  await expect.poll(() => server.ccRequests.at(-1)?.get('keyword')).toBe('陈')
  await page.getByRole('option', { name: '陈运营', exact: true }).click()
  await expect(editor.getByText('陈运营', { exact: true })).toBeVisible()
  await editor.getByRole('textbox', { name: '标题' }).click()
  await expect(page.locator('.create-dialog')).toHaveClass(/is-fullscreen/)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)
  expect((await editor.getByTestId('ad-production-save').boundingBox())?.height).toBeGreaterThanOrEqual(44)
  await page.screenshot({ path: testInfo.outputPath('author-correction-mobile.png'), animations: 'disabled' })
  await editor.getByTestId('ad-production-save').click()
  await expect(editor).toBeHidden()
  await expect(page.getByTestId('ad-production-card-7')).toContainText('更新北门店二维码')
  expect(server.detailRequests).toEqual([7, 7])
  expect(server.designerRequests).toHaveLength(0)
  expect(server.ccRequests.at(-1)?.get('ad_id')).toBe('7')
  expect(server.ccRequests.at(-1)?.get('kind')).toBe('MERCHANT_AD')
  expect(server.updates[0].get('cc_user_ids')).toBe('[21]')
  expect(server.updates).toHaveLength(1)
  expect(server.updates[0].get('status')).toBe('IN_PROGRESS')
  expect(server.updates[0].get('content')).toBe(record.content)
  expect(server.updates[0].get('content_format')).toBe('PLAIN')
  expect(server.updates[0].has('receiver_id')).toBe(false)
  expect(server.updates[0].has('completed_by_id')).toBe(false)
  expect(server.updates[0].has('processing_result')).toBe(false)
})

test('a creator retains their draft after a completion conflict and reloads a read-only detail', async ({ page }) => {
  const server = await mockAdProduction(page, { permissions: creatorPermissions, completeOnUpdate: true })
  await page.goto('/#/ad-productions')
  await page.getByTestId('ad-production-edit-7').click()
  const editor = page.getByRole('dialog', { name: '编辑物料制作需求' })
  const title = editor.getByRole('textbox', { name: '标题' })
  await title.fill('待保存的标题更正')
  await editor.getByTestId('ad-production-save').click()
  const conflict = page.getByRole('dialog', { name: '数据已被其他用户修改' })
  await expect(conflict.getByText('已完成', { exact: true })).toBeVisible()
  await conflict.getByRole('button', { name: '重新加载服务器版本' }).click()
  const confirm = page.getByRole('dialog', { name: '重新加载服务器版本？' })
  await confirm.getByRole('button', { name: '继续编辑' }).click()
  await expect(conflict).toBeHidden()
  await expect(title).toHaveValue('待保存的标题更正')
  await editor.getByTestId('ad-production-save').click()
  await expect(conflict.getByText('已完成', { exact: true })).toBeVisible()
  await conflict.getByRole('button', { name: '重新加载服务器版本' }).click()
  await confirm.getByRole('button', { name: '放弃修改并重新加载' }).click()
  await expect(editor).toBeHidden()
  const detail = page.getByRole('dialog', { name: '物料制作详情' })
  await expect(detail.getByText('该需求已完成，无法继续修改。')).toBeVisible()
  await expect(detail.getByTestId('ad-production-detail-edit')).toHaveCount(0)
  await expect(detail.getByTestId('ad-production-change-status')).toHaveCount(0)
  await detail.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page.getByRole('row', { name: /中央公园店海报设计/ })).toContainText('已完成')
  await expect(page.getByTestId('ad-production-edit-7')).toHaveCount(0)
  expect(server.updates.map(update => update.get('revision'))).toEqual(['1', '1'])
})

test('mobile edit-only users can complete an assigned record with accessible form actions', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const server = await mockAdProduction(page, {
    designers,
    permissions: editorPermissions,
    actor: { id: 13, username: 'completer', display_name: '秦设计', data_scope: 'SELF' },
    record: {
      title: '中央公园店海报', publisher_display_name: '张运营',
      due_at: '2026-11-30T09:30:00Z', receiver_id: 13, receiver_display_name: '秦设计',
    },
  })
  await page.goto('/#/ad-productions')
  await page.getByRole('navigation', { name: '扩展导航' }).getByRole('button', { name: '运营协作' }).press('Enter')
  await expect(page.getByRole('menuitem', { name: '物料制作', exact: true })).toBeVisible()
  await page.getByRole('menuitem', { name: '物料制作', exact: true }).click()
  await page.getByRole('button', { name: '筛选', exact: true }).click()
  const filters = page.getByRole('dialog', { name: '筛选物料制作需求', exact: true })
  await expect(filters).toBeVisible()
  await filters.getByRole('button', { name: '查询', exact: true }).click()
  await expect(filters).toBeHidden()
  const card = page.getByTestId('ad-production-card-7')
  await expect(card).toBeVisible()
  await expect(card).toContainText('中央公园店海报')
  await expect(card).toContainText('截止时间')
  await expect(card).toContainText('秦设计')
  await expect(page.getByTestId('ad-production-create')).toHaveCount(0)
  await expect(page.locator('.el-loading-mask:visible')).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath('ad-list-mobile.png'), animations: 'disabled' })
  await card.click()
  const detail = page.getByRole('dialog', { name: '物料制作详情' })
  await expect(recordPublisher(detail)).toHaveText('张运营')
  await expect(detail.getByText(record.issuer, { exact: true })).toHaveCount(0)
  await detail.getByRole('button', { name: '更改状态', exact: true }).click()
  const editor = page.getByRole('dialog', { name: '更改状态' })
  await expect(editor.locator('.create-dialog')).toBeVisible()
  await expect(editor.locator('.create-dialog')).not.toHaveClass(/is-fullscreen/)
  await expect(recordPublisher(editor)).toHaveText('张运营')
  await expect(editor.locator('[datetime="2026-11-26T01:00:00Z"]')).toHaveText(/09:00/)
  await expect(editor.getByRole('combobox', { name: '状态' })).toBeVisible()
  await expect(editor.getByRole('combobox', { name: '实际完成人' })).toHaveCount(0)
  await expect(editor.getByRole('combobox', { name: '需求接收人' })).toHaveCount(0)
  await expect(editor.getByRole('textbox', { name: '需求内容' })).toHaveCount(0)
  await editor.getByTestId('ad-production-status').locator('.el-select__wrapper').click()
  await page.getByRole('option', { name: '已完成', exact: true }).click()
  const completedBy = editor.getByRole('combobox', { name: '实际完成人' })
  await expect(completedBy).toBeEnabled()
  await expect(editor.getByText('搜索人员', { exact: true })).toBeVisible()
  await completedBy.fill('秦')
  await page.getByRole('option', { name: '秦设计', exact: true }).click()

  await page.keyboard.press('Escape')
  await page.keyboard.press('Escape')
  const keepEditing = page.getByRole('button', { name: '继续编辑' })
  await keepEditing.click()
  await expect(keepEditing).toBeHidden()
  await expect(editor.getByText('已完成', { exact: true })).toBeVisible()
  await expect(editor.getByText('秦设计', { exact: true })).toBeVisible()
  const save = editor.getByRole('button', { name: '保存', exact: true })
  await expect(save).toBeInViewport()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)
  await page.screenshot({ path: testInfo.outputPath('ad-status-mobile.png'), animations: 'disabled' })
  await save.click()
  await expect(editor).toBeHidden()
  await expect(card).toContainText('已完成')
  expect(server.updates).toHaveLength(0)
  expect(server.statusUpdates).toEqual([{ revision: 1, status: 'COMPLETED', completed_by_id: 13 }])
  await expect(detail.getByRole('heading', { name: '中央公园店海报', exact: true })).toBeVisible()
  await expect(detail.getByText('已完成', { exact: true })).toBeVisible()
  await expect(detail.getByText('秦设计', { exact: true })).toHaveCount(2)
})

test('retrying designer options keeps the publication draft and defaults the only receiver', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const server = await mockAdProduction(page, { designers: designers.slice(0, 1), designerFailures: 1 })
  await page.goto('/#/ad-productions')
  await page.getByTestId('ad-production-create').click()
  const editor = page.getByRole('dialog', { name: '发布物料制作需求' })
  await expect(editor.getByText('人员选项加载失败')).toBeVisible()
  await expect(editor.getByRole('combobox', { name: '实际完成人' })).toHaveCount(0)

  const title = editor.getByRole('textbox', { name: '标题' })
  await title.fill('门店海报')
  const content = editor.getByRole('textbox', { name: '需求内容' })
  await content.fill('已验收的门店海报')
  await editor.getByRole('button', { name: '重试', exact: true }).click()
  await expect(editor.getByText('人员选项加载失败')).toBeHidden()
  await expect(content).toHaveText('已验收的门店海报')
  await expect(title).toHaveValue('门店海报')
  await expect(editor.getByText('林设计', { exact: true })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('ad-create-desktop.png'), animations: 'disabled' })

  await editor.getByRole('button', { name: '发布需求', exact: true }).click()
  await expect(editor).toBeHidden()
  expect(server.creations).toHaveLength(1)
  expect(server.creations[0].get('receiver_id')).toBe('12')
  expect(server.creations[0].has('due_at')).toBe(false)
  expect(server.creations[0].has('cc_user_ids')).toBe(false)
})

test('a historical completed record keeps its original receiver and unrecorded completer', async ({ page }) => {
  const server = await mockAdProduction(page, {
    record: { status: 'COMPLETED', receiver_id: 19, receiver_display_name: '历史接单人' },
    designers: designers.slice(0, 1),
  })
  await page.goto('/#/ad-productions')
  await page.getByTestId('ad-production-edit-7').click()
  const editor = page.getByRole('dialog', { name: '编辑物料制作需求' })
  await expect(editor.getByText('历史接单人（原记录）', { exact: true })).toBeVisible()
  await expect(editor.getByRole('combobox', { name: '实际完成人' })).toBeEnabled()
  await expect(editor.getByText('搜索人员', { exact: true })).toBeVisible()

  await editor.getByRole('textbox', { name: '需求内容' }).fill('补充原制作说明')
  await editor.getByRole('button', { name: '保存', exact: true }).click()
  await expect(editor).toBeHidden()
  expect(server.updates).toHaveLength(1)
  expect(server.updates[0].has('receiver_id')).toBe(false)
  expect(server.updates[0].has('completed_by_id')).toBe(false)
  expect(server.updates[0].has('title')).toBe(false)
  expect(server.updates[0].has('due_at')).toBe(false)
  expect(server.updates[0].has('clear_due_at')).toBe(false)
  expect(server.updates[0].get('work_date')).toBe(record.work_date)

  await page.getByTestId('ad-production-view-7').click()
  const detail = page.getByRole('dialog', { name: '物料制作详情' })
  await expect(detail.getByText('历史接单人', { exact: true })).toBeVisible()
  await expect(detail.getByText('实际完成人', { exact: true })).toBeVisible()
  await expect(detail.locator('dl > div').filter({ hasText: '实际完成人' }).getByText('—', { exact: true })).toBeVisible()
})

test('clearing a receiver is an edit and reopening does not submit a completer', async ({ page }) => {
  const server = await mockAdProduction(page, {
    record: {
      status: 'COMPLETED', receiver_id: 12, receiver_display_name: '林设计',
      completed_by_id: 13, completed_by_display_name: '秦设计', due_at: '2026-11-30T09:30:00Z',
    },
    designers,
  })
  await page.goto('/#/ad-productions')
  await page.getByTestId('ad-production-edit-7').click()
  const editor = page.getByRole('dialog', { name: '编辑物料制作需求' })
  const receiver = editor.locator('.el-form-item').filter({ has: page.getByRole('combobox', { name: '需求接收人' }) }).locator('.el-select')
  await expect(receiver.getByText('林设计', { exact: true })).toBeVisible()
  await expect(editor.getByRole('combobox', { name: '需求接收人' })).toBeEnabled()
  await receiver.hover()
  await receiver.locator('.el-select__clear').click()
  await editor.getByRole('button', { name: '取消', exact: true }).click()
  const close = page.getByRole('dialog', { name: '放弃未保存的修改？' })
  await expect(close.getByText('当前修改尚未保存，离开后将丢失。')).toBeVisible()
  await close.getByRole('button', { name: '继续编辑' }).click()
  await expect(close).toBeHidden()

  await editor.getByTestId('ad-production-status').locator('.el-select__wrapper').click()
  await page.getByRole('option', { name: '进行中', exact: true }).click()
  await expect(editor.getByRole('combobox', { name: '实际完成人' })).toHaveCount(0)
  const deadline = editor.getByRole('combobox', { name: '截止时间' })
  await expect(deadline).toHaveValue('2026-11-30 17:30')
  await deadline.fill('')
  await deadline.press('Tab')
  await editor.getByRole('button', { name: '保存', exact: true }).click()
  await expect(editor).toBeHidden()
  expect(server.updates).toHaveLength(1)
  expect(server.updates[0].get('receiver_id')).toBe('0')
  expect(server.updates[0].has('completed_by_id')).toBe(false)
  expect(server.updates[0].get('clear_due_at')).toBe('true')
  expect(server.updates[0].has('due_at')).toBe(false)
  expect(server.updates[0].get('content_format')).toBe('PLAIN')
  expect(server.updates[0].get('content')).toBe(record.content)
})

test('a status conflict keeps the draft until the receiver confirms a reload', async ({ page }) => {
  const server = await mockAdProduction(page, { designers: designers.slice(0, 1), conflictOnStatus: true })
  await page.goto('/#/ad-productions')
  await page.getByTestId('ad-production-view-7').click()
  await page.getByTestId('ad-production-change-status').click()
  const editor = page.getByRole('dialog', { name: '更改状态' })
  const select = editor.getByTestId('ad-production-status').locator('.el-select__wrapper')
  const completed = page.getByRole('option', { name: '已完成', exact: true })
  await select.click()
  await completed.click()
  await expect(editor.getByText('林设计', { exact: true })).toBeVisible()
  await editor.getByRole('button', { name: '保存', exact: true }).click()
  const conflict = page.getByRole('dialog', { name: '数据已被其他用户修改' })
  await expect(conflict.getByText('物料制作记录已更新。', { exact: false })).toBeVisible()
  await expect(recordPublisher(conflict)).toHaveText('用户 #1')
  await expect(conflict.getByText('邮寄中', { exact: true })).toBeVisible()
  expect(server.statusUpdates).toEqual([{ revision: 1, status: 'COMPLETED', completed_by_id: 12 }])
  await conflict.getByRole('button', { name: '重新加载服务器版本' }).click()
  const reload = page.getByRole('dialog', { name: '重新加载服务器版本？' })
  await reload.getByRole('button', { name: '继续编辑' }).click()
  await expect(conflict).toBeHidden()
  await expect(editor.getByText('已完成', { exact: true })).toBeVisible()
  await expect(editor.getByText('林设计', { exact: true })).toBeVisible()
  await editor.getByRole('button', { name: '保存', exact: true }).click()
  await expect(conflict.getByText('邮寄中', { exact: true })).toBeVisible()
  expect(server.statusUpdates).toHaveLength(2)
  expect(server.statusUpdates[1].revision).toBe(1)
  await conflict.getByRole('button', { name: '重新加载服务器版本' }).click()
  await reload.getByRole('button', { name: '放弃修改并重新加载' }).click()
  await expect(conflict).toBeHidden()
  await expect(editor.getByText('邮寄中', { exact: true })).toBeVisible()
  await select.click()
  await completed.click()
  await editor.getByRole('button', { name: '保存', exact: true }).click()
  await expect(editor).toBeHidden()
  expect(server.statusUpdates[2]).toEqual({ revision: 2, status: 'COMPLETED', completed_by_id: 12 })
})

test('merchant and material lists share publishing but keep each kind separate', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const server = await mockAdProduction(page, { designers })
  await page.goto('/#/ad-productions')
  await expect(page.getByTestId('ad-production-view-7')).toBeVisible()
  expect(server.requests.at(-1)?.get('kind')).toBe('MATERIAL')
  await page.getByRole('complementary', { name: '侧边导航' }).getByRole('link', { name: '商家广告', exact: true }).click()
  await expect(page.getByRole('heading', { name: '商家广告', exact: true })).toBeVisible()
  await expect(page.getByText('暂无商家广告记录')).toBeVisible()
  expect(server.requests.at(-1)?.get('kind')).toBe('MERCHANT_AD')
  await page.getByRole('button', { name: '发布商家广告需求', exact: true }).click()
  const form = page.getByRole('dialog', { name: '发布商家广告需求' })
  await expect(form.getByText(/^(下发人|需求发布人)$/)).toHaveCount(0)
  await expect(form.getByLabel(/^(下发人|需求发布人)$/)).toHaveCount(0)
  await expect(form.getByText(/老机器和新机器的二维码（含集合码）/)).toBeVisible()
  await form.getByRole('textbox', { name: '标题' }).fill('中央公园店更新二维码')
  await form.getByRole('textbox', { name: '需求内容' }).fill('更新新机器的门店二维码和集合码。')
  await form.getByRole('combobox', { name: '需求接收人' }).fill('林')
  await page.getByRole('option', { name: '林设计', exact: true }).click()
  await form.locator('.el-select:has(#ad-production-cc-users) .el-select__wrapper').click()
  await page.getByRole('option', { name: '陈运营', exact: true }).click()
  await form.getByRole('textbox', { name: '标题' }).click()
  await page.screenshot({ path: testInfo.outputPath('merchant-ad-publish-desktop.png'), animations: 'disabled' })
  await form.getByRole('button', { name: '发布需求', exact: true }).click()
  await expect(form).toBeHidden()
  await expect(page.getByRole('row', { name: /中央公园店更新二维码/ }).getByText('未处理', { exact: true })).toBeVisible()
  expect(server.creations[0].get('kind')).toBe('MERCHANT_AD')
  expect(server.creations[0].get('receiver_id')).toBe('12')
  expect(server.creations[0].get('cc_user_ids')).toBe('[21]')
  expect(server.ccRequests.at(-1)?.get('kind')).toBe('MERCHANT_AD')
  expect(server.ccRequests.at(-1)?.has('ad_id')).toBe(false)
  expect(server.creations[0].has('issuer')).toBe(false)
  expect(server.creations[0].has('created_by')).toBe(false)
  expect(server.creations[0].has('publisher_display_name')).toBe(false)
  await page.getByTestId('ad-production-edit-8').click()
  const editor = page.getByRole('dialog', { name: '编辑商家广告需求' })
  await expect(recordPublisher(editor)).toHaveText('测试管理员')
  await editor.getByTestId('ad-production-status').locator('.el-select__wrapper').click()
  await expect(page.getByRole('option', { name: '邮寄中', exact: true })).toHaveCount(0)
  await page.getByRole('option', { name: '已处理', exact: true }).click()
  await editor.getByRole('combobox', { name: '实际完成人' }).fill('秦')
  await page.getByRole('option', { name: '秦设计', exact: true }).click()
  await editor.getByRole('textbox', { name: '处理结果' }).fill('已换码，门店已核对。')
  await editor.getByRole('button', { name: '保存', exact: true }).click()
  await expect(editor).toBeHidden()
  expect(server.updates[0].has('kind')).toBe(false)
  expect(server.updates[0].has('cc_user_ids')).toBe(false)
  expect(server.updates[0].get('processing_result')).toBe('已换码，门店已核对。')
  expect(server.updates[0].get('completed_by_id')).toBe('13')
  await page.getByTestId('ad-production-view-8').click()
  const detail = page.getByRole('dialog', { name: '商家广告详情' })
  await expect(recordPublisher(detail)).toHaveText('测试管理员')
  await expect(detail.getByText('已换码，门店已核对。')).toBeVisible()
  await expect(detail.locator('dl > div').filter({ hasText: '抄送人' }).locator('dd')).toHaveText('陈运营')
  await expect(detail.getByText('秦设计', { exact: true })).toBeVisible()
  await detail.getByRole('button', { name: '关闭', exact: true }).click()
  await page.getByRole('complementary', { name: '侧边导航' }).getByRole('link', { name: '物料制作', exact: true }).click()
  await expect(page.getByTestId('ad-production-view-7')).toBeVisible()
  await expect(page.getByTestId('ad-production-view-8')).toHaveCount(0)
  expect(server.requests.at(-1)?.get('kind')).toBe('MATERIAL')
})

test('mobile material editors search CC users and can explicitly clear existing selections', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const server = await mockAdProduction(page, {
    record: { cc_users: [{ id: 30, display_name: '历史抄送人' }] },
  })
  await page.goto('/#/ad-productions')
  const openEditor = async () => {
    await page.getByTestId('ad-production-card-7').click()
    await page.getByRole('dialog', { name: '物料制作详情' }).getByRole('button', { name: '编辑', exact: true }).click()
  }
  await openEditor()
  const editor = page.getByRole('dialog', { name: '编辑物料制作需求' })
  const ccControl = editor.locator('.el-select:has(#ad-production-cc-users) .el-select__wrapper')
  await expect(editor.getByText('历史抄送人', { exact: true })).toBeVisible()
  await ccControl.click()
  await editor.getByRole('combobox', { name: '抄送人' }).fill('陆')
  await expect.poll(() => server.ccRequests.at(-1)?.get('keyword')).toBe('陆')
  await page.getByRole('option', { name: '陆门店', exact: true }).click()
  await expect(editor.getByText('陆门店', { exact: true })).toBeVisible()
  await editor.getByRole('textbox', { name: '标题' }).click()
  expect((await ccControl.boundingBox())?.height).toBeGreaterThanOrEqual(44)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)
  await page.screenshot({ path: testInfo.outputPath('ad-cc-edit-mobile.png'), animations: 'disabled' })
  await editor.getByRole('button', { name: '保存', exact: true }).click()
  await expect(editor).toBeHidden()
  expect(server.ccRequests.at(-1)?.get('ad_id')).toBe('7')
  expect(server.updates[0].get('cc_user_ids')).toBe('[30,22]')
  expect(server.updates[0].get('revision')).toBe('1')

  await openEditor()
  const removeCcTags = ccControl.locator('.el-tag__close')
  await expect(removeCcTags).toHaveCount(2)
  await removeCcTags.first().click()
  await removeCcTags.first().click()
  await editor.getByRole('button', { name: '取消', exact: true }).click()
  await page.getByRole('button', { name: '继续编辑', exact: true }).click()
  await expect(removeCcTags).toHaveCount(0)
  await editor.getByRole('button', { name: '保存', exact: true }).click()
  await expect(editor).toBeHidden()
  expect(server.updates[1].get('cc_user_ids')).toBe('[]')
  expect(server.updates[1].get('revision')).toBe('2')
})

for (const scenario of [
  { kind: 'MATERIAL', label: '物料制作', notice: 'AD_PRODUCTION_MATERIAL_CC', path: 'material', width: 1440 },
  { kind: 'MERCHANT_AD', label: '商家广告', notice: 'AD_PRODUCTION_MERCHANT_CC', path: 'merchant-ad', width: 375 },
] as const) {
  test(`${scenario.label} CC notification opens only the record without module permissions`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: scenario.width, height: 900 })
    const server = await mockAdProduction(page, {
      permissions: [],
      actor: { id: 21, username: 'cc-user', display_name: '陈运营', data_scope: 'SELF' },
      notice: scenario.notice,
      blockedRecordIds: [8],
      record: {
        kind: scenario.kind, title: '抄送的门店资料', cc_users: ccUsers,
        content: '<p>制作需求说明</p><img data-file-id="41">',
        content_format: 'HTML',
        images: [{ file_id: 40, original_name: 'poster.png', mime_type: 'image/png', size: png.length, created_at: record.created_at, created_by: 1 }],
      },
    })
    await page.goto('/#/notifications')
    await page.getByRole('button', { name: /请查看需求详情/ }).click()
    await expect(page).toHaveURL(`/#/notifications/${scenario.path}/7`)
    await expect(page.getByRole('heading', { name: `${scenario.label}详情` })).toBeVisible()
    const detail = page.getByTestId('ad-production-notification-detail')
    await expect(detail.getByRole('heading', { name: '抄送的门店资料' })).toBeVisible()
    await expect(detail.getByText('制作需求说明')).toBeVisible()
    await expect(detail.locator('dl > div').filter({ hasText: '抄送人' }).locator('dd')).toHaveText('陈运营、陆门店')
    await expect(detail.getByRole('button', { name: '查看大图' })).toBeVisible()
    await expect(detail.getByRole('button', { name: '预览 poster.png' })).toBeVisible()
    await expect(page.getByRole('button', { name: /^(编辑|更改状态|发布需求|移除)$/ })).toHaveCount(0)
    await expect(page.getByTestId('ad-production-list')).toHaveCount(0)
    expect(server.requests).toEqual([])
    expect(server.detailRequests).toEqual([7])
    expect(server.imageRequests).toEqual(expect.arrayContaining([
      '/api/v1/ad-productions/7/images/40', '/api/v1/ad-productions/7/content-images/41',
    ]))
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(scenario.width)
    await page.screenshot({ path: testInfo.outputPath('ad-cc-detail.png'), animations: 'disabled' })
    await page.getByRole('button', { name: '返回通知中心' }).click()
    await expect(page.getByRole('heading', { name: '通知中心' })).toBeVisible()
    await expect(page.getByText('0 条未读')).toBeVisible()

    await page.goto(`/#/notifications/${scenario.path}/8`)
    await expect(detail.getByRole('alert')).toContainText('无法查看此记录')
    await expect(detail.getByText('制作需求说明')).toHaveCount(0)
    await page.goto(scenario.kind === 'MATERIAL' ? '/#/ad-productions' : '/#/merchant-ads')
    await expect(page.getByRole('heading', { name: '无权访问' })).toBeVisible()
    expect(server.detailRequests).toEqual([7, 8])
    expect(server.requests).toEqual([])
  })
}

test('merchant list blocks legacy material responses and recovers when the service returns the proper list', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const server = await mockAdProduction(page)
  let legacy = true
  await page.route(/\/api\/v1\/ad-productions\?/, route => {
    if (!legacy) return route.fallback()
    const legacyRecord = { ...record, kind: undefined }
    return route.fulfill({ json: { items: [legacyRecord], total: 1, page: 1, page_size: 20 } })
  })

  await page.goto('/#/ad-productions')
  await expect(page.getByTestId('ad-production-view-7')).toBeVisible()
  await expect(page.getByTestId('ad-production-create')).toBeEnabled()
  await page.getByRole('complementary', { name: '侧边导航' }).getByRole('link', { name: '商家广告', exact: true }).click()
  const error = page.getByRole('alert').filter({ hasText: '商家广告记录加载失败' })
  await expect(error).toContainText('请联系管理员检查接口版本，修复后重新加载。')
  await expect(page.getByTestId('ad-production-view-7')).toHaveCount(0)
  await expect(page.getByText('共 1 条', { exact: true })).toHaveCount(0)
  await expect(page.getByTestId('ad-production-create')).toBeDisabled()
  expect(server.detailRequests).toEqual([])

  legacy = false
  await error.getByRole('button', { name: '重新加载' }).click()
  await expect(page.getByText('暂无商家广告记录')).toBeVisible()
  await expect(page.getByTestId('ad-production-create')).toBeEnabled()
  expect(server.requests.at(-1)?.get('kind')).toBe('MERCHANT_AD')
})

test('mobile notification opens the shared merchant drawer and records actual processing', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const server = await mockAdProduction(page, {
    permissions: merchantEditorPermissions,
    actor: { id: 12, username: 'designer', display_name: '林设计', data_scope: 'SELF' },
    record: {
      kind: 'MERCHANT_AD', title: '南门店机器交接', publisher_display_name: '张运营',
      receiver_id: 12, receiver_display_name: '林设计', status: 'NOT_STARTED',
    },
    designers: designers.slice(0, 1),
    notice: true,
  })
  await page.goto('/#/notifications')
  await page.getByRole('button', { name: '运营协作' }).click()
  await expect(page.getByRole('menuitem', { name: '商家广告', exact: true })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: '物料制作', exact: true })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: /新的商家广告制作需求/ }).click()
  await expect(page).toHaveURL(/#\/merchant-ads\?record_id=7$/)
  const detail = page.getByRole('dialog', { name: '商家广告详情' })
  await expect(detail.getByRole('heading', { name: '南门店机器交接' })).toBeVisible()
  await expect(recordPublisher(detail)).toHaveText('张运营')
  await expect(detail.getByText('未处理', { exact: true })).toBeVisible()
  await expect(page.getByTestId('ad-production-create')).toHaveCount(0)
  expect(server.requests.at(-1)?.get('kind')).toBe('MERCHANT_AD')
  expect(server.detailRequests).toEqual([7])
  await detail.getByRole('button', { name: '更改状态' }).click()
  const editor = page.getByRole('dialog', { name: '更改状态' })
  await expect(recordPublisher(editor)).toHaveText('张运营')
  await editor.getByTestId('ad-production-status').locator('.el-select__wrapper').click()
  await expect(page.getByRole('option', { name: '处理中', exact: true })).toBeVisible()
  await expect(page.getByRole('option', { name: '邮寄中', exact: true })).toHaveCount(0)
  await page.getByRole('option', { name: '已处理', exact: true }).click()
  await editor.getByRole('button', { name: '保存', exact: true }).click()
  await expect(editor.getByText('处理结果须填写 1–4000 字')).toBeVisible()
  expect(server.statusUpdates).toHaveLength(0)
  const result = '已交接南门店。\n新二维码和集合码已更新。'
  await editor.getByRole('textbox', { name: '处理结果' }).fill(result)
  await expect(editor.getByText('处理结果须填写 1–4000 字')).toBeHidden()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)
  expect((await editor.getByRole('button', { name: '保存', exact: true }).boundingBox())?.height).toBeGreaterThanOrEqual(44)
  await page.screenshot({ path: testInfo.outputPath('merchant-ad-processing-mobile.png'), animations: 'disabled' })
  await editor.getByRole('button', { name: '保存', exact: true }).click()
  await expect(editor).toBeHidden()
  expect(server.designerRequests.map(query => query.get('kind'))).toEqual(['MERCHANT_AD'])
  await expect(detail.getByText('已处理', { exact: true })).toBeVisible()
  await expect(recordPublisher(detail)).toHaveText('张运营')
  await expect(detail.getByText(result)).toBeVisible()
  expect(server.statusUpdates).toEqual([{ revision: 1, status: 'COMPLETED', completed_by_id: 12, processing_result: result }])
  await detail.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page).toHaveURL(/#\/merchant-ads$/)
  await expect(detail).toBeHidden()
  await expect(page.getByTestId('ad-production-card-7')).toContainText('已处理')
  await page.screenshot({ path: testInfo.outputPath('merchant-ad-list-mobile.png'), animations: 'disabled' })
})

test('a legacy merchant notice is read-only for a former receiver who can still read through CC', async ({ page }) => {
  const server = await mockAdProduction(page, {
    permissions: merchantEditorPermissions,
    actor: { id: 12, username: 'designer', display_name: '林设计', data_scope: 'SELF' },
    record: {
      kind: 'MERCHANT_AD', title: '南门店机器交接', receiver_id: 13, receiver_display_name: '秦设计',
      cc_users: [{ id: 12, display_name: '林设计' }],
    },
    notice: true,
  })
  await page.route(url => url.pathname === '/api/v1/ad-productions', route =>
    route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 20 } }),
  )
  await page.goto('/#/notifications')
  await page.getByRole('button', { name: /新的商家广告制作需求/ }).click()
  await expect(page).toHaveURL(/#\/merchant-ads\?record_id=7$/)
  const detail = page.getByRole('dialog', { name: '商家广告详情' })
  await expect(detail.getByRole('heading', { name: '南门店机器交接' })).toBeVisible()
  await expect(detail.locator('dl > div').filter({ hasText: '抄送人' }).locator('dd')).toHaveText('林设计')
  await expect(detail.getByTestId('ad-production-detail-edit')).toHaveCount(0)
  await expect(detail.getByTestId('ad-production-change-status')).toHaveCount(0)
  expect(server.detailRequests).toEqual([7])
})

test('merchant detail links reject repeated IDs, other types, and out-of-scope records', async ({ page }) => {
  const server = await mockAdProduction(page, { permissions: ['ops.merchant_ad.view'], blockedRecordIds: [8] })
  await page.goto('/#/merchant-ads?record_id=7&record_id=8')
  await expect(page.getByText('暂无商家广告记录')).toBeVisible()
  expect(server.detailRequests).toEqual([])
  await page.goto('/#/merchant-ads?record_id=7')
  const detail = page.getByRole('dialog', { name: '商家广告详情' })
  await expect(detail.getByText('商家广告记录加载失败')).toBeVisible()
  await expect(detail.getByText(record.content)).toHaveCount(0)
  await expect(detail.getByRole('button', { name: '更改状态' })).toHaveCount(0)
  await page.goto('/#/merchant-ads?record_id=8')
  await expect.poll(() => server.detailRequests).toEqual([7, 8])
  await expect(detail.getByText('商家广告记录加载失败')).toBeVisible()
  await expect(detail.getByText(record.content)).toHaveCount(0)
})

test('material-only permission cannot open merchant details', async ({ page }) => {
  const server = await mockAdProduction(page, { permissions: creatorPermissions })
  await page.goto('/#/merchant-ads?record_id=7')
  await expect(page.getByRole('heading', { name: '无权访问' })).toBeVisible()
  await expect(page).toHaveURL(/#\/forbidden$/)
  expect(server.detailRequests).toEqual([])
  expect(server.requests).toEqual([])
})

test('merchant-only creator falls back to merchant ads and cannot open material details', async ({ page }) => {
  const server = await mockAdProduction(page, {
    permissions: merchantCreatorPermissions,
    record: { kind: 'MERCHANT_AD', title: '更换商家二维码', status: 'NOT_STARTED' },
    designers,
  })
  await page.goto('/#/')
  await expect(page).toHaveURL(/#\/merchant-ads$/)
  const navigation = page.getByRole('complementary', { name: '侧边导航' })
  await expect(navigation.getByRole('link', { name: '商家广告', exact: true })).toBeVisible()
  await expect(navigation.getByRole('link', { name: '物料制作', exact: true })).toHaveCount(0)
  await expect(page.getByTestId('ad-production-view-7')).toBeVisible()
  await expect(page.getByTestId('ad-production-edit-7')).toBeVisible()
  await page.getByRole('button', { name: '发布商家广告需求', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '发布商家广告需求' })).toBeVisible()
  await expect.poll(() => server.designerRequests.map(query => query.get('kind'))).toEqual(['MERCHANT_AD'])

  await page.goto('/#/ad-productions?record_id=7')
  await expect(page).toHaveURL(/#\/forbidden$/)
  await expect(page.getByRole('heading', { name: '无权访问' })).toBeVisible()
  expect(server.requests.map(query => query.get('kind'))).toEqual(['MERCHANT_AD'])
  expect(server.detailRequests).toEqual([])
})

test('create and edit actions use the active module permissions when both lists are visible', async ({ page }) => {
  await mockAdProduction(page, { permissions: [...editorPermissions, ...merchantCreatorPermissions] })
  const navigation = page.getByRole('complementary', { name: '侧边导航' })
  await page.goto('/#/merchant-ads')
  await expect(page.getByTestId('ad-production-create')).toBeEnabled()
  await navigation.getByRole('link', { name: '物料制作', exact: true }).click()
  await expect(page.getByTestId('ad-production-edit-7')).toBeVisible()
  await expect(page.getByTestId('ad-production-create')).toHaveCount(0)
})
