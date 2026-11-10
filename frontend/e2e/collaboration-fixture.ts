import type { Route } from '@playwright/test'

// Only the independent read panels added to existing routes. Keep each test's
// workflow/participants, selector data and all business writes under its own mock.
export async function mockReadPanels(route: Route): Promise<boolean> {
  if (route.request().method() !== 'GET') return false
  const path = new URL(route.request().url()).pathname
  let data: unknown
  if (/\/(feedbacks|requirements|versions)\/\d+\/activities$/.test(path)) data = []
  else if (/\/versions\/\d+\/release-batches$/.test(path)) data = { version_id: Number(path.split('/')[4]), version_revision: 1, system_id: 1, release_frozen: false, legacy_unrecorded: false, coverage_count: 0, items: [], total: 0, page: 1, page_size: 20 }
  else if (/\/versions\/\d+\/release-targets$/.test(path)) data = []
  else if (path === '/api/v1/announcements/notice') data = { unread_count: 0, latest: null, important: null }
  else if (path === '/api/v1/systems/options') data = [{ id: 1, name: '系统甲' }]
  else return false
  await route.fulfill({ status: 200, json: data })
  return true
}

// Older route/layout regressions share minimal data for the newly visible panels.
// Real business transitions are covered by release.spec.ts against PostgreSQL.
export async function mockCollaboration(route: Route): Promise<boolean> {
  if (await mockReadPanels(route)) return true
  if (route.request().method() !== 'GET') return false
  const path = new URL(route.request().url()).pathname
  let data: unknown
  if (/\/(requirements|versions)\/filter-options\/(participants|versions|owners)$/.test(path)) {
    const selectedId = Number(new URL(route.request().url()).searchParams.get('selected_id'))
    data = { items: selectedId > 0 ? [{ id: selectedId, label: `可见选项 #${selectedId}` }] : [], total: selectedId > 0 ? 1 : 0, page: 1, page_size: 20 }
  }
  else if (/\/requirements\/\d+\/workflow$/.test(path)) data = { revision: 1, content_revision: 1, confirmed_revision: 1, needs_confirmation: false, legacy_completed: true, design_status: 'NOT_REQUIRED', paused_from: null, records: [] }
  else if (/\/requirements\/\d+\/participants$/.test(path)) data = { revision: 1, participants: ['CONFIRM', 'DEVELOP', 'ACCEPT'].map(role => ({ user_id: 1, role, display_name: '环节人员', active: true })) }
  else if (/\/feedbacks\/\d+\/collaboration$/.test(path)) data = { revision: 1, recipients: [{ id: 1, display_name: '接收人' }], handler_id: null, accepted_by: null, accepted_at: null }
  else if (path === '/api/v1/me/mail-preferences') data = { revision: 1, mode: 'TASKS', email: null, verified: false, pending_email: null, smtp_enabled: false }
  else return false
  await route.fulfill({ status: 200, json: data })
  return true
}
