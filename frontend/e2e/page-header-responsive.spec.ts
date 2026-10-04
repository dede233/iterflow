import { expect, test, type Page } from '@playwright/test'

// Include both sides of the mobile and tablet/desktop boundaries.
const widths = [375, 390, 767, 768, 820, 1024, 1199, 1200, 1201, 1280, 1440]
const title = 'Preview v1.8 acceptance 20261003 %_\\ · 平板公共头部布局验收'
const date = '2026-10-03T00:00:00Z'
const feedback = {
  id: 1, feedback_no: 'FB-20261003-0001', title, feedback_type: 'OTHER', urgency: 'NORMAL',
  status: 'NEW', description: '仅用于公共头部布局回归', submitter_id: 1,
  system_id: null, module_id: null, main_requirement_id: null, duplicate_of_id: null,
  created_at: date, updated_at: date, updated_by: 1, revision: 1,
}
const requirement = {
  id: 2, requirement_no: 'REQ-20261003-0001', title, requirement_type: 'FEATURE',
  source: 'DIRECT', priority: 'P0', status: 'DONE', owner_id: 1, current_version_id: 3,
  description: '仅用于公共头部布局回归', system_id: null, module_id: null,
  created_at: date, updated_at: date, updated_by: 1, revision: 1,
}
const version = {
  id: 3, version_no: 'V1.8-header-test', name: title, status: 'READY', owner_id: 1,
  description: null, planned_release_date: '2026-10-04', released_at: null,
  created_at: date, updated_at: date, updated_by: 1, revision: 1,
}

async function fixture(page: Page) {
  const unexpected: string[] = []
  await page.addInitScript(() => {
    localStorage.setItem('iterflow.access_token', 'page-header-test-access')
    localStorage.setItem('iterflow.refresh_token', 'page-header-test-refresh')
  })
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    const responses: Record<string, unknown> = {
      '/api/v1/auth/me': {
        id: 1, username: 'header-tester', display_name: '布局验收管理员', status: 'ACTIVE',
        must_change_password: false, data_scope: 'ALL', permission_codes: ['*'], role_ids: [], revision: 1,
      },
      '/api/v1/notifications/unread-count': { unread_count: 0 },
      '/api/v1/systems': { systems: [], modules: [] },
      '/api/v1/feedbacks/1': feedback,
      '/api/v1/feedbacks/1/attachments': [],
      '/api/v1/feedbacks/1/comments': [],
      '/api/v1/requirements/2': requirement,
      '/api/v1/requirements/2/feedbacks': [],
      '/api/v1/versions/3': version,
      '/api/v1/versions/3/requirements': {
        version_id: 3, items: [requirement],
        stats: { total: 1, completed: 1, completion_rate: 1, by_status: { DONE: 1 } },
      },
      '/api/v1/releases': { items: [], total: 0, page: 1, page_size: 20 },
    }
    if (!(path in responses) || route.request().method() !== 'GET') {
      unexpected.push(`${route.request().method()} ${path}`)
      return route.fulfill({ status: 500, json: { message: 'Unexpected request in layout regression' } })
    }
    return route.fulfill({ status: 200, json: responses[path] })
  })
  return unexpected
}

const screens = [
  { name: 'Feedback', path: '/feedbacks/1', buttons: ['编辑', '转需求', '受理', '标记重复', '无法复现', '关闭'] },
  { name: 'Requirement', path: '/requirements/2', buttons: ['编辑', '重新开发'] },
  { name: 'Version', path: '/versions/3', buttons: ['编辑', '发布', '退回测试'] },
]

for (const width of widths) {
  for (const screen of screens) {
    test(`PageHeader ${screen.name} actions and readable title at ${width}px`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 900 })
      const errors: string[] = []
      page.on('pageerror', error => errors.push(error.message))
      const unexpected = await fixture(page)
      await page.goto(`/#${screen.path}`)
      const header = page.locator('.page-header')
      const heading = header.getByRole('heading', { name: title, exact: true })
      await expect(heading).toBeVisible()
      for (const name of screen.buttons) await expect(header.getByRole('button', { name, exact: true })).toBeVisible()

      // The public bug has six NEW-feedback actions. Do not weaken the fixture by hiding any.
      await expect(header.getByRole('button')).toHaveCount(screen.buttons.length)
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth))
        .toBeLessThanOrEqual(width + 1)
      const bounds = await header.evaluate(element => {
        const rect = (node: Element) => {
          const r = node.getBoundingClientRect()
          return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width }
        }
        return {
          scrollWidth: document.documentElement.scrollWidth, viewportWidth: window.innerWidth,
          header: rect(element), heading: rect(element.querySelector('h1')!),
          text: rect(element.querySelector('.page-header__text')!),
          actions: rect(element.querySelector('.page-header__actions')!),
          controls: [...element.querySelectorAll('.page-header__actions a, .page-header__actions button')].map(rect),
        }
      })
      expect(bounds.heading.width, 'title must not collapse to a single-character column')
        .toBeGreaterThanOrEqual(Math.min(240, bounds.header.width * 0.5))
      for (const rect of [bounds.actions, ...bounds.controls]) {
        expect(rect.left).toBeGreaterThanOrEqual(0)
        expect(rect.right).toBeLessThanOrEqual(width + 1)
      }
      if (width < 1200) {
        expect(bounds.actions.top, 'tablet/mobile actions follow the title in DOM and visual order')
          .toBeGreaterThanOrEqual(bounds.text.bottom)
      }

      // Every action remains reachable by keyboard in DOM order, including the final Close.
      const back = header.getByRole('link', { name: '返回列表', exact: true })
      await back.focus()
      for (const name of screen.buttons) {
        await page.keyboard.press('Tab')
        await expect(header.getByRole('button', { name, exact: true })).toBeFocused()
      }
      const last = header.getByRole('button', { name: screen.buttons.at(-1)!, exact: true })
      await last.click({ trial: true })
      if (screen.name === 'Feedback') {
        await page.keyboard.press('Enter')
        const dialog = page.getByRole('dialog')
        await expect(dialog).toBeVisible()
        await dialog.getByRole('button', { name: '取消', exact: true }).click()
        await expect(dialog).not.toBeVisible()
        await expect(last).toBeFocused()
      }
      await testInfo.attach('PageHeader geometry', { body: JSON.stringify({ width, ...bounds }), contentType: 'application/json' })
      if (screen.name === 'Feedback' && [375, 768, 1440].includes(width)) {
        await page.screenshot({ path: testInfo.outputPath(`page-header-${width}.png`), fullPage: true })
      }
      expect(unexpected).toEqual([])
      expect(errors).toEqual([])
    })
  }
}
