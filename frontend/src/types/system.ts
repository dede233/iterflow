import type { DataScope, UserStatus } from './auth'

export interface UserItem {
  id: number
  username: string
  display_name: string
  email: string | null
  mobile: string | null
  status: UserStatus
  revision: number
  role_ids: number[]
}

export interface RoleItem {
  id: number
  code: string
  name: string
  data_scope: DataScope
  enabled: boolean
  is_system: boolean
  revision: number
  permission_ids: number[]
}

export interface PermissionItem {
  id: number
  code: string
  name: string
  category: string
}
