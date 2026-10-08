import { expect, test } from '@playwright/test'

const timestamp = '2026-10-08T00:00:00Z'
const version = (id: number) => ({
  id, version_no: `V${id}`, name: `版本详情 ${id}`, status: 'PLANNING', owner_id: 1,
  planned_release_date: null, released_at: null, description: `版本描述 ${id}`,
  created_at: timestamp, updated_at: timestamp, updated_by: 1, revision: 3,
})
const requirement = (id: number) => ({
  id, requirement_no: `REQ-${id}`, title: `需求详情 ${id}`, requirement_type: 'FEATURE',
  source: 'DIRECT', priority: 'P2', status: 'DRAFT', system_id: null, module_id: null,
  owner_id: 1, current_version_id: null, description: `需求描述 ${id}`, acceptance_criteria: null,
  created_at: timestamp, updated_at: timestamp, updated_by: 1, revision: 4,
})
const feedback = (id: number) => ({
  id, feedback_no: `FB-${id}`, title: `反馈详情 ${id}`, feedback_type: 'NEW_FEATURE',
  urgency: 'NORMAL', status: 'NEW', system_id: null, module_id: null, submitter_id: 1,
  description: `反馈描述 ${id}`, expected_result: null, actual_result: null,
  reproduce_steps: null, main_requirement_id: null, duplicate_of_id: null,
  created_at: timestamp, updated_at: timestamp, updated_by: 1, revision: 2,
})

const cases = [
  { path: '/versions', label: '版本', item: version, titleField: 'name', editField: '版本名称', action: '开始开发', nextStatus: 'DEVELOPING' },
  { path: '/requirements', label: '需求', item: requirement, titleField: 'title', editField: '标题', action: '确认', nextStatus: 'CONFIRMED' },
  { path: '/feedbacks', label: '反馈', item: feedback, titleField: 'title', editField: '标题', action: '受理', nextStatus: 'ACCEPTED' },
] as const

for (const width of [1280, 390]) {
  for (const entry of cases) {
    test(`${entry.label} drawer loads selected IDs and expands with list context at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      const requests: string[] = []
      const unexpected: string[] = []
      const errors: string[] = []
      page.on('pageerror', error => errors.push(error.message))
      await page.addInitScript(() => {
        localStorage.setItem('iterflow.access_token', 'drawer-test-access')
        localStorage.setItem('iterflow.refresh_token', 'drawer-test-refresh')
      })
      await page.route('**/api/v1/**', async route => {
        const url = new URL(route.request().url())
        const path = url.pathname.replace('/api/v1', '')
        requests.push(url.pathname + url.search)
        let response: unknown
        if (path === '/auth/me') {
          response = {
            id: 1, username: 'admin', display_name: '系统管理员', email: null,
            status: 'ACTIVE', revision: 1, must_change_password: false,
            data_scope: 'ALL', role_ids: [1], permission_codes: ['*'],
          }
        } else if (path === '/notifications/unread-count') response = { unread_count: 0 }
        else if (path === '/systems') response = { systems: [], modules: [] }
        else if (path === entry.path) response = { items: [entry.item(7), entry.item(8)], total: 2, page: 2, page_size: 20 }
        else if (path === '/releases') response = { items: [], total: 0, page: 1, page_size: 20 }
        else if (path === `${entry.path}/7` || path === `${entry.path}/8`) response = entry.item(Number(path.split('/').at(-1)))
        else if (entry.path === '/versions' && /^\/versions\/[78]\/requirements$/.test(path)) {
          response = { version_id: Number(path.split('/')[2]), items: [], stats: { total: 0, by_status: {}, completed: 0, completion_rate: 0 } }
        } else if (/^\/feedbacks\/[78]\/(attachments|comments)$/.test(path) || /^\/requirements\/[78]\/feedbacks$/.test(path)) response = []
        else {
          unexpected.push(path)
          return route.fulfill({ status: 422, json: { detail: 'Unexpected ID or API request' } })
        }
        return route.fulfill({ status: 200, json: response })
      })
      await page.goto(`/#${entry.path}?page=2&keyword=context`)
      for (const id of [7, 8]) {
        const row = width >= 768 ? page.locator('.el-table__body tr.el-table__row').filter({ hasText: `${entry.label}详情 ${id}` }) : page.getByText(`${entry.label}详情 ${id}`, { exact: true })
        await row.click()
        const drawer = page.getByRole('dialog', { name: `${entry.label}详情`, exact: true })
        await expect(drawer.getByRole('heading', { name: `${entry.label}详情 ${id}`, exact: true })).toBeVisible()
        await expect(page).toHaveURL(new RegExp(`#${entry.path}\\?page=2&keyword=context$`))
        expect(requests).toContain(`/api/v1${entry.path}/${id}`)
        if (entry.path === '/versions') {
          expect(requests).toContain(`/api/v1/versions/${id}/requirements`)
          expect(requests.some(path => path.startsWith('/api/v1/releases?') && path.includes(`version_id=${id}`))).toBe(true)
        }
        if (id === 7) {
          await drawer.getByRole('link', { name: '返回列表', exact: true }).click()
          await expect(drawer).not.toBeVisible()
          await expect(page).toHaveURL(new RegExp(`#${entry.path}\\?page=2&keyword=context$`))
        } else {
          await drawer.getByRole('button', { name: '新标签/全屏直达', exact: true }).click()
          await expect(page).toHaveURL(new RegExp(`#${entry.path}/8\\?`))
          await expect(page.getByRole('heading', { name: `${entry.label}详情 8`, exact: true })).toBeVisible()
          await page.getByRole('link', { name: '返回列表', exact: true }).click()
          await expect(page).toHaveURL(new RegExp(`#${entry.path}\\?page=2&keyword=context$`))
        }
      }
      expect(unexpected).toEqual([])
      expect(errors).toEqual([])
    })

    test(`${entry.label} drawer edits refresh the filtered list without losing context at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      let item: Record<string, unknown> = entry.item(7)
      const initialStatus = String(item.status)
      const listQueries: Record<string, string>[] = []
      const writes: { path: string; body: Record<string, unknown> }[] = []
      const unexpected: string[] = []
      const errors: string[] = []
      page.on('pageerror', error => errors.push(error.message))
      await page.addInitScript(() => {
        localStorage.setItem('iterflow.access_token', 'drawer-edit-access')
        localStorage.setItem('iterflow.refresh_token', 'drawer-edit-refresh')
      })
      await page.route('**/api/v1/**', async route => {
        const request = route.request()
        const url = new URL(request.url())
        const path = url.pathname.slice('/api/v1'.length)
        const json = (body: unknown) => route.fulfill({ status: 200, json: body })
        if (path === '/auth/me') return json({ id: 1, username: 'admin', display_name: '管理员', status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'ALL', role_ids: [1], permission_codes: ['*'] })
        if (path === '/notifications/unread-count') return json({ unread_count: 0 })
        if (path === '/systems') return json({ systems: [], modules: [] })
        if (path.startsWith('/editing/')) return json({ existing_editor: null })
        if (path === entry.path) {
          listQueries.push(Object.fromEntries(url.searchParams))
          const visible = item.status === url.searchParams.get('status')
          // Keep page 2 valid when the edited record leaves the active status filter.
          return json({ items: [...(visible ? [item] : []), entry.item(8)], total: visible ? 41 : 40, page: 2, page_size: 20 })
        }
        if (request.method() === 'PATCH' && (path === `${entry.path}/7` || path === `${entry.path}/7/status`)) {
          const body = request.postDataJSON() as Record<string, unknown>
          writes.push({ path, body })
          expect(body.revision).toBe(item.revision)
          item = { ...item, ...body, revision: Number(item.revision) + 1 }
          return json(item)
        }
        if (path === `${entry.path}/7`) return json(item)
        if (path === '/versions/7/requirements') return json({ version_id: 7, items: [], stats: { total: 0, by_status: {}, completed: 0, completion_rate: 0 } })
        if (path === '/releases') return json({ items: [], total: 0, page: 1, page_size: 20 })
        if (['/feedbacks/7/attachments', '/feedbacks/7/comments', '/requirements/7/feedbacks'].includes(path)) return json([])
        unexpected.push(`${request.method()} ${path}`)
        return route.fulfill({ status: 500, json: { detail: 'Unexpected request' } })
      })
      const listURL = `/#${entry.path}?page=2&status=${initialStatus}`
      await page.goto(listURL)
      const originalTitle = `${entry.label}详情 7`
      await page.getByText(originalTitle, { exact: true }).click()
      let drawer = page.getByRole('dialog', { name: `${entry.label}详情`, exact: true })
      await drawer.getByRole('button', { name: '编辑', exact: true }).click()
      const editor = page.getByRole('dialog', { name: `编辑${entry.label}`, exact: true })
      const newTitle = `${entry.label}更新后的标题`
      await editor.locator('.el-form-item').filter({ hasText: entry.editField }).locator('input').fill(newTitle)
      await editor.getByRole('button', { name: '保存', exact: true }).click()
      await expect(drawer.getByRole('heading', { name: newTitle, exact: true })).toBeVisible()
      await expect.poll(() => listQueries.length).toBe(2)
      await drawer.locator('.el-drawer__close-btn').click()
      await expect(drawer).not.toBeVisible()
      await expect(page.getByText(newTitle, { exact: true })).toBeVisible()
      await expect(page.getByText(originalTitle, { exact: true })).toHaveCount(0)
      await page.getByText(newTitle, { exact: true }).click()
      drawer = page.getByRole('dialog', { name: `${entry.label}详情`, exact: true })
      await drawer.getByRole('button', { name: entry.action, exact: true }).click()
      const statusDialog = page.getByRole('dialog', { name: entry.action, exact: true })
      await statusDialog.getByRole('button', { name: '确定', exact: true }).click()
      await expect(statusDialog).not.toBeVisible()
      await expect.poll(() => listQueries.length).toBe(3)
      await drawer.locator('.el-drawer__close-btn').click()
      await expect(drawer).not.toBeVisible()
      await expect(page.getByText(newTitle, { exact: true })).toHaveCount(0)
      await expect(page).toHaveURL(new RegExp(`#${entry.path}\\?page=2&status=${initialStatus}$`))
      expect(listQueries).toEqual(Array.from({ length: 3 }, () => ({ page: '2', page_size: '20', status: initialStatus })))
      expect(writes).toHaveLength(2)
      expect(writes[0]?.body[entry.titleField]).toBe(newTitle)
      expect(writes[1]?.body.status).toBe(entry.nextStatus)
      expect(unexpected).toEqual([])
      expect(errors).toEqual([])
    })
  }
}
