export type DataScope = 'SELF' | 'ALL' | 'TEAM'
export type UserStatus = 'ACTIVE' | 'DISABLED' | 'LOCKED'

export interface CurrentUser {
  id: number
  username: string
  display_name: string
  email: string | null
  status: UserStatus
  revision: number
  role_ids: number[]
  permission_codes: string[]
  data_scope: DataScope
  must_change_password: boolean
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  must_change_password: boolean
}
