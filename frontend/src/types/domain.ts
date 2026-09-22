export interface PageResult<T> { items: T[]; page: number; page_size: number; total: number }
export interface Feedback {
  id: number
  feedback_no: string
  title: string
  feedback_type: string
  urgency: string
  status: string
  system_id?: number | null
  module_id?: number | null
  submitter_id: number
  description: string
  expected_result?: string | null
  actual_result?: string | null
  reproduce_steps?: string | null
  main_requirement_id?: number | null
  duplicate_of_id?: number | null
  created_at: string
  updated_at: string
  updated_by?: number | null
  revision: number
}

export interface FeedbackListParams {
  page?: number
  page_size?: number
  status?: string
  feedback_type?: string
  urgency?: string
  system_id?: number | null
  module_id?: number | null
  keyword?: string
}

export interface FeedbackCreatePayload {
  title: string
  feedback_type: string
  urgency: string
  system_id?: number | null
  module_id?: number | null
  description: string
  expected_result?: string | null
  actual_result?: string | null
  reproduce_steps?: string | null
}

export interface FeedbackUpdatePayload {
  title?: string
  feedback_type?: string
  urgency?: string
  system_id?: number | null
  module_id?: number | null
  description?: string
  expected_result?: string | null
  actual_result?: string | null
  reproduce_steps?: string | null
  revision: number
}

export interface FeedbackStatusChangePayload {
  status: string
  revision: number
  reason?: string | null
  duplicate_of_id?: number | null
}

export interface BusinessSystemItem { id: number; code: string; name: string; enabled: boolean }
export interface BusinessModuleItem {
  id: number
  system_id: number
  code: string
  name: string
  enabled: boolean
}

export interface AttachmentItem {
  file_id: number
  original_name: string
  size: number
  mime_type: string
  created_at: string
  created_by?: number | null
}

export interface CommentItem {
  id: number
  entity_type: string
  entity_id: number
  content: string
  created_at: string
  created_by?: number | null
}
export interface Requirement {
  id: number
  requirement_no: string
  title: string
  requirement_type: string
  source: string
  priority: string
  status: string
  system_id?: number | null
  module_id?: number | null
  owner_id?: number | null
  current_version_id?: number | null
  description: string
  acceptance_criteria?: string | null
  created_at: string
  updated_at: string
  updated_by?: number | null
  revision: number
}

export interface RequirementCreatePayload {
  title: string
  requirement_type: string
  priority: string
  description: string
  acceptance_criteria?: string | null
  version_id?: number | null
  version_revision?: number | null
}

export interface RequirementUpdatePayload {
  title?: string
  requirement_type?: string
  priority?: string
  description?: string
  acceptance_criteria?: string | null
  revision: number
}

export interface LinkedFeedback {
  feedback_id: number
  feedback_no: string
  title: string
  status: string
  is_primary: boolean
}

export interface ConvertFeedbackPayload {
  type: 'CREATE_NEW' | 'LINK_EXISTING'
  revision: number
  requirement_title?: string
  requirement_type?: string
  priority?: string
  description?: string
  acceptance_criteria?: string | null
  requirement_id?: number | null
}
export interface VersionItem {
  id: number
  version_no: string
  name: string
  status: string
  owner_id?: number | null
  planned_release_date?: string | null
  released_at?: string | null
  description?: string | null
  created_at?: string
  updated_at?: string
  updated_by?: number | null
  revision: number
}

export interface VersionCreatePayload {
  version_no: string
  name: string
  planned_release_date?: string | null
  description?: string | null
}

export interface VersionUpdatePayload {
  name?: string
  planned_release_date?: string | null
  description?: string | null
  revision: number
}

export interface VersionStats {
  total: number
  by_status: Record<string, number>
  completed: number
  completion_rate: number
}

export interface VersionRequirementsResult {
  version_id: number
  stats: VersionStats
  items: Requirement[]
}

export interface PublishCheckItem {
  type: string
  passed: boolean
  message: string
  blocking_requirements?: { id: number; requirement_no: string; status: string }[]
}

export interface PublishCheckResult {
  passed: boolean
  checks: PublishCheckItem[]
}

export interface ReleaseItem {
  id: number
  version_id: number
  released_at: string
  result: string
  release_notes: string
  rollback_notes?: string | null
  created_at: string
  created_by?: number | null
  revision: number
}

export interface AuditOperator {
  id: number
  username: string
  display_name: string
}

export interface AuditItem {
  id: number
  entity_type: string
  entity_id?: number | null
  action: string
  operator?: AuditOperator | null
  before?: Record<string, unknown> | null
  after?: Record<string, unknown> | null
  created_at: string
}

export interface AuditListParams {
  page?: number
  size?: number
  entity_type?: string
  entity_id?: number
  action?: string
  operator_id?: number
  time_from?: string
  time_to?: string
}

export interface AuditPage {
  items: AuditItem[]
  page: number
  size: number
  total: number
}

export type NotificationType = 'SYSTEM' | 'FEEDBACK' | 'REQUIREMENT' | 'VERSION' | 'RELEASE'
export interface NotificationItem { id:number; type:NotificationType; title:string; content:string; entity_type?:string|null; entity_id?:number|null; read_at?:string|null; created_at:string }
