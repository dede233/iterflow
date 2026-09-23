import type { components } from './openapi.generated'

export type UserItem = components['schemas']['UserOut']
export type RoleItem = components['schemas']['RoleOut']
export type PermissionItem = components['schemas']['PermissionOut']
export type UserCreatePayload = components['schemas']['UserCreate']
export type UserUpdatePayload = components['schemas']['UserUpdate']
export type UserStatusChangePayload = components['schemas']['UserStatusChange']
export type UserRoleUpdatePayload = components['schemas']['UserRoleUpdate']
export type RoleCreatePayload = components['schemas']['RoleCreate']
export type RoleUpdatePayload = components['schemas']['RoleUpdate']
export type RolePermissionUpdatePayload = components['schemas']['RolePermissionUpdate']
export type RoleDeleteOut = components['schemas']['RoleDeleteOut']
