export type DashboardDataScope = 'SELF' | 'ALL'

export interface DashboardFeedbackOverview {
  pending_count: number
  total_count: number
  by_status: Record<string, number>
}

export interface DashboardRequirementOverview {
  active_count: number
  total_count: number
  by_status: Record<string, number>
}

export interface DashboardVersionItem {
  id: number
  version_no: string
  name: string
  status: string
  planned_release_date: string | null
  updated_at: string
}

export interface DashboardVersionOverview {
  active_count: number
  total_count: number
  by_status: Record<string, number>
  recent_active_versions: DashboardVersionItem[]
}

export interface DashboardReleaseItem {
  id: number
  version_id: number
  version_no: string
  version_name: string
  released_at: string
  result: string
}

export interface DashboardReleaseOverview {
  total_count: number
  recent_releases: DashboardReleaseItem[]
}

export interface DashboardOverview {
  data_scope: DashboardDataScope
  feedback: DashboardFeedbackOverview | null
  requirements: DashboardRequirementOverview | null
  versions: DashboardVersionOverview | null
  releases: DashboardReleaseOverview | null
}
