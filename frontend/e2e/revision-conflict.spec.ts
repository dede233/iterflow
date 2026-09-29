import { expect, test, type BrowserContext } from '@playwright/test'

const date = '2026-09-29T00:00:00Z'
const initial = {
  id: 1, feedback_no: 'FB-1', title: '初始反馈', feedback_type: 'OTHER', urgency: 'NORMAL',
  status: 'NEW', system_id: null, module_id: null, submitter_id: 1,
  description: '初始描述', expected_result: null, actual_result: null, reproduce_steps: null,
  main_requirement_id: null, duplicate_of_id: null, created_at: date, updated_at: date,
  updated_by: 1, revision: 1,
}

function actor(id: number) {
  return {
    id, username: `editor-${id}`, display_name: `编辑者${id}`, email: null,
    status: 'ACTIVE', revision: 1, must_change_password: false, data_scope: 'ALL', role_ids: [1],
    permission_codes: ['rd.feedback.view', 'rd.feedback.edit'],
  }
}

async function mockApi(context: BrowserContext, actorId: number, state: { feedback: typeof initial; writes: { actor: number; revision: number }[]; ends: number[] }) {
  await context.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'conflict-test-access')
    localStorage.setItem('iterflow.refresh_token', 'conflict-test-refresh')
  })
  await context.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const method = route.request().method()
    if (path === '/api/v1/auth/me') return route.fulfill({ status: 200, json: actor(actorId) })
    if (path === '/api/v1/feedbacks/1' && method === 'GET') return route.fulfill({ status: 200, json: state.feedback })
    if (path === '/api/v1/feedbacks/1' && method === 'PATCH') {
      const body = route.request().postDataJSON() as { title: string; revision: number }
      state.writes.push({ actor: actorId, revision: body.revision })
      if (body.revision !== state.feedback.revision) {
        return route.fulfill({
          status: 409,
          json: {
            code: 40910, message: '反馈已被其他用户修改', request_id: null,
            data: {
              current_revision: state.feedback.revision,
              current_updated_at: state.feedback.updated_at,
              current_updated_by: state.feedback.updated_by,
            },
          },
        })
      }
      state.feedback = { ...state.feedback, title: body.title, revision: body.revision + 1, updated_by: actorId, updated_at: '2026-09-29T01:00:00Z' }
      return route.fulfill({ status: 200, json: state.feedback })
    }
    if (path === '/api/v1/feedbacks/1/attachments' || path === '/api/v1/feedbacks/1/comments') return route.fulfill({ status: 200, json: [] })
    if (path.startsWith('/api/v1/editing/')) {
      const operation = path.split('/').at(-1)
      if (operation === 'end') state.ends.push(actorId)
      return route.fulfill({ status: 200, json: operation === 'start' ? { existing_editor: null } : { ok: true, existing_editor: null } })
    }
    throw new Error(`Unexpected ${method} ${path}`)
  })
}

function editTitle(page: import('@playwright/test').Page) {
  return page.getByRole('dialog', { name: '编辑反馈' }).locator('.el-form-item').filter({ hasText: '标题' }).locator('input')
}

test('two editors keep the stale draft until B explicitly reloads the server version', async ({ browser }) => {
  const state = { feedback: { ...initial }, writes: [] as { actor: number; revision: number }[], ends: [] as number[] }
  const a = await browser.newContext()
  const b = await browser.newContext()
  try {
    await mockApi(a, 1, state)
    await mockApi(b, 2, state)
    const pageA = await a.newPage()
    const pageB = await b.newPage()
    await pageA.goto('/#/feedbacks/1')
    await pageB.goto('/#/feedbacks/1')
    await pageA.getByRole('button', { name: '编辑', exact: true }).click()
    await pageB.getByRole('button', { name: '编辑', exact: true }).click()
    await editTitle(pageA).fill('A 保存的标题')
    await editTitle(pageB).fill('B 的本地输入')
    await pageA.getByRole('dialog', { name: '编辑反馈' }).getByRole('button', { name: '保存' }).click()
    await expect(pageA.getByRole('dialog', { name: '编辑反馈' })).toHaveCount(0)
    await pageB.getByRole('dialog', { name: '编辑反馈' }).getByRole('button', { name: '保存' }).click()
    const conflict = pageB.getByRole('dialog', { name: '数据已被其他用户修改' })
    await expect(conflict).toBeVisible()
    await expect(pageB.getByText('服务器版本已变化，请查看冲突详情')).toHaveCount(0)
    await expect(conflict).toContainText('A 保存的标题')
    await expect(conflict).toContainText('用户 #1')
    await expect(editTitle(pageB)).toHaveValue('B 的本地输入')
    expect(state.ends).not.toContain(2)
    await conflict.getByRole('button', { name: '关闭并人工处理' }).click()
    await expect(editTitle(pageB)).toHaveValue('B 的本地输入')
    await pageB.getByRole('dialog', { name: '编辑反馈' }).getByRole('button', { name: '保存' }).click()
    await expect(conflict).toBeVisible()
    expect(state.writes.filter((write) => write.actor === 2).map((write) => write.revision)).toEqual([1, 1])
    await conflict.getByRole('button', { name: '重新加载服务器版本' }).click()
    await expect(conflict).toHaveCount(0)
    await expect(editTitle(pageB)).toHaveValue('A 保存的标题')
    expect(state.ends).not.toContain(2)
    await editTitle(pageB).fill('B 核对后保存')
    await pageB.getByRole('dialog', { name: '编辑反馈' }).getByRole('button', { name: '保存' }).click()
    await expect(pageB.getByRole('dialog', { name: '编辑反馈' })).toHaveCount(0)
    expect(state.writes.filter((write) => write.actor === 2).map((write) => write.revision)).toEqual([1, 1, 2])
    await expect.poll(() => state.ends.filter((id) => id === 2).length).toBe(1)
  } finally {
    await a.close()
    await b.close()
  }
})

for (const width of [375, 390, 768, 1280, 1440]) {
  test(`revision conflict dialog fits ${width}px with long server text`, async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width, height: 900 } })
    const state = { feedback: { ...initial, title: '很长的服务器标题'.repeat(20), description: '服务器详细描述'.repeat(80), revision: 2 }, writes: [] as { actor: number; revision: number }[], ends: [] as number[] }
    try {
      await mockApi(context, 2, state)
      const page = await context.newPage()
      await page.goto('/#/feedbacks/1')
      await page.getByRole('button', { name: '编辑', exact: true }).click()
      state.feedback = { ...state.feedback, revision: 3 }
      await page.getByRole('dialog', { name: '编辑反馈' }).getByRole('button', { name: '保存' }).click()
      const conflict = page.getByRole('dialog', { name: '数据已被其他用户修改' })
      await expect(conflict).toBeVisible()
      const box = await conflict.boundingBox()
      expect(box).not.toBeNull()
      expect(box!.x).toBeGreaterThanOrEqual(0)
      expect(box!.x + box!.width).toBeLessThanOrEqual(width + 1)
      expect(box!.y + box!.height).toBeLessThanOrEqual(901)
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    } finally {
      await context.close()
    }
  })
}
