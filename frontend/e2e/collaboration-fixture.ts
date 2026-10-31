import type { Route } from '@playwright/test'

// Older route/layout regressions share minimal data for the newly visible panels.
// Real business transitions are covered by release.spec.ts against PostgreSQL.
export async function mockCollaboration(route: Route): Promise<boolean> {
  if (route.request().method() !== 'GET') return false
  const path = new URL(route.request().url()).pathname
  let data: unknown
  if (/\/requirements\/\d+\/workflow$/.test(path)) data = { revision: 1, content_revision: 1, confirmed_revision: 1, needs_confirmation: false, legacy_completed: true, design_status: 'NOT_REQUIRED', paused_from: null, records: [] }
  else if (/\/requirements\/\d+\/participants$/.test(path)) data = { revision: 1, participants: ['CONFIRM', 'DEVELOP', 'ACCEPT'].map(role => ({ user_id: 1, role, display_name: '环节人员', active: true })) }
  else if (/\/feedbacks\/\d+\/collaboration$/.test(path)) data = { revision: 1, recipients: [{ id: 1, display_name: '接收人' }], handler_id: null, accepted_by: null, accepted_at: null }
  else if (path === '/api/v1/me/mail-preferences') data = { revision: 1, mode: 'TASKS', email: null, verified: false, pending_email: null, smtp_enabled: false }
  else return false
  await route.fulfill({ status: 200, json: data })
  return true
}
