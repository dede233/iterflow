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
export interface Requirement { id:number; requirement_no:string; title:string; requirement_type:string; source:string; priority:string; status:string; owner_id?:number|null; current_version_id?:number|null; description:string; acceptance_criteria?:string|null; revision:number }
export interface VersionItem { id:number; version_no:string; name:string; status:string; owner_id?:number|null; planned_release_date?:string|null; released_at?:string|null; revision:number }
export type NotificationType = 'SYSTEM' | 'FEEDBACK' | 'REQUIREMENT' | 'VERSION' | 'RELEASE'
export interface NotificationItem { id:number; type:NotificationType; title:string; content:string; entity_type?:string|null; entity_id?:number|null; read_at?:string|null; created_at:string }
