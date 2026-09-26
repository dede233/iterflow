<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createUser, listUsers, updateUser, updateUserRoles, updateUserStatus } from '@/api/users'
import { listRoles } from '@/api/roles'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useResponsive } from '@/composables/useResponsive'
import UserRoleAssignmentDrawer from '@/components/UserRoleAssignmentDrawer.vue'
import {
  buildUserBasicUpdatePayload,
  buildUserRoleUpdateRequest,
  canLoadRoleDefinitions,
  canOperatorChangeUserStatus,
  isCurrentUserSuperAdmin,
  isSuperAdminRole,
  statusConfirmationMessage,
} from '@/components/userRoleAssignment'
import { usePermission } from '@/composables/usePermission'
import { useAuthStore } from '@/stores/auth'
import type { RoleItem, UserItem } from '@/types/system'

const { can } = usePermission()
const { isMobile } = useResponsive()
const auth = useAuthStore()
const rows = ref<UserItem[]>([])
const roles = ref<RoleItem[]>([])
const loading = ref(false)
const failed = ref(false)
const dialogVisible = ref(false)
const editingUser = ref<UserItem | null>(null)
const saving = ref(false)
const roleDrawerVisible = ref(false)
const roleUser = ref<UserItem | null>(null)
const roleSaving = ref(false)
const form = reactive({
  username: '',
  display_name: '',
  email: '' as string | null,
  mobile: '' as string | null,
  password: '',
  role_ids: [] as number[],
})
const hasAllScope = computed(() => auth.user?.data_scope === 'ALL')
const canReadRoleDefinitions = computed(
  () => canLoadRoleDefinitions(auth.user, can),
)
const canAssignUserRoles = computed(() => hasAllScope.value && can('sys.user.role.assign'))
const canCreateUsers = computed(() => hasAllScope.value && can('sys.user.create') && canAssignUserRoles.value)
const canEditUsers = computed(() => can('sys.user.edit'))
const canChangeUserStatus = computed(() => hasAllScope.value && can('sys.user.status'))
const operatorIsSuperAdmin = computed(() => isCurrentUserSuperAdmin(auth.user, roles.value))

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    const users = await listUsers()
    rows.value = users.items
    roles.value = canReadRoleDefinitions.value
      ? (await listRoles()).filter((role) => role.enabled)
      : []
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

function resetForm(): void {
  Object.assign(form, { username: '', display_name: '', email: '', mobile: '', password: '', role_ids: [] })
}

function openCreate(): void {
  editingUser.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(user: UserItem): void {
  editingUser.value = user
  Object.assign(form, {
    username: user.username,
    display_name: user.display_name,
    email: user.email ?? '',
    mobile: user.mobile ?? '',
    password: '',
    role_ids: [],
  })
  dialogVisible.value = true
}

function openRoles(user: UserItem): void {
  roleUser.value = user
  roleDrawerVisible.value = true
}

async function save(): Promise<void> {
  saving.value = true
  try {
    const email = form.email?.trim() || null
    const mobile = form.mobile?.trim() || null
    if (!editingUser.value) {
      await createUser({
        username: form.username.trim(),
        display_name: form.display_name.trim(),
        email,
        mobile,
        password: form.password,
        role_ids: form.role_ids,
      })
      ElMessage.success('用户已创建')
    } else {
      await updateUser(
        editingUser.value.id,
        buildUserBasicUpdatePayload(
          { display_name: form.display_name, email, mobile },
          editingUser.value.revision,
        ),
      )
      ElMessage.success('用户已更新')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function saveRoles(roleIds: number[]): Promise<void> {
  const user = roleUser.value
  if (!user) return
  roleSaving.value = true
  try {
    const request = buildUserRoleUpdateRequest(user, roleIds)
    const updated = await updateUserRoles(request.userId, {
      role_ids: request.roleIds,
      revision: request.revision,
    })
    roleUser.value = updated
    roleDrawerVisible.value = false
    ElMessage.success('用户角色已更新')
    await load()
  } finally {
    roleSaving.value = false
  }
}

function mayChangeStatus(user: UserItem): boolean {
  return (
    canChangeUserStatus.value &&
    canOperatorChangeUserStatus(user, roles.value, operatorIsSuperAdmin.value)
  )
}

async function toggleStatus(user: UserItem): Promise<void> {
  const status = user.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE'
  const action = status === 'ACTIVE' ? '启用' : '停用'
  await ElMessageBox.confirm(statusConfirmationMessage(user, roles.value, status), `${action}用户`, {
    confirmButtonText: action,
    cancelButtonText: '取消',
    type: 'warning',
  })
  await updateUserStatus(user.id, { status, revision: user.revision })
  ElMessage.success(`用户已${action}`)
  await load()
}

function roleNames(user: UserItem): string {
  if (!canReadRoleDefinitions.value) {
    const roleIds = user.role_ids ?? []
    return roleIds.length ? `已分配 ${roleIds.length} 个角色` : '未分配'
  }
  const labels = (user.role_ids ?? [])
    .map((roleId) => roles.value.find((role) => role.id === roleId)?.name)
    .filter((name): name is string => Boolean(name))
  return labels.length ? labels.join('、') : '未分配'
}

onMounted(load)
</script>

<template>
  <section class="page">
    <PageHeader title="用户管理" description="管理账号、状态与角色分配。" eyebrow="系统治理">
      <template #actions><el-button v-if="canCreateUsers" type="primary" @click="openCreate">创建用户</el-button></template>
    </PageHeader>

    <ErrorState v-if="failed" title="用户列表加载失败" description="请检查网络后重试。" retry-label="重新加载" @retry="load" />
    <SectionCard v-else title="账号列表" :description="`共 ${rows.length} 个账号`" :padded="false">
    <el-table v-if="!isMobile" v-loading="loading" :data="rows" row-key="id">
      <el-table-column prop="username" label="用户名" min-width="130" />
      <el-table-column prop="display_name" label="姓名" min-width="130" />
      <el-table-column prop="email" label="邮箱" min-width="180" />
      <el-table-column label="角色" min-width="180">
        <template #default="scope">{{ roleNames(scope.row) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="scope">
          <StatusTag :status="scope.row.status" :label="scope.row.status === 'ACTIVE' ? '启用' : '停用'" />
        </template>
      </el-table-column>
      <el-table-column v-if="canEditUsers || canAssignUserRoles || canChangeUserStatus" label="操作" width="240" fixed="right">
        <template #default="scope">
          <el-button v-if="canEditUsers" link type="primary" @click="openEdit(scope.row)">编辑</el-button>
          <el-button v-if="canAssignUserRoles" link type="primary" @click="openRoles(scope.row)">配置角色</el-button>
          <el-button v-if="mayChangeStatus(scope.row)" link :type="scope.row.status === 'ACTIVE' ? 'danger' : 'success'" @click="toggleStatus(scope.row)">
            {{ scope.row.status === 'ACTIVE' ? '停用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
      <template #empty><EmptyState description="暂无用户" compact /></template>
    </el-table>
    <div v-else v-loading="loading" class="user-cards">
      <article v-for="user in rows" :key="user.id" class="user-card">
        <div class="user-card__head">
          <div><strong>{{ user.display_name }}</strong><span class="user-card__id">{{ user.username }}</span></div>
          <StatusTag :status="user.status" :label="user.status === 'ACTIVE' ? '启用' : '停用'" size="sm" />
        </div>
        <div class="user-card__details"><span>角色</span><span>{{ roleNames(user) }}</span></div>
        <div v-if="user.email" class="user-card__details"><span>邮箱</span><span>{{ user.email }}</span></div>
        <div v-if="canEditUsers || canAssignUserRoles || mayChangeStatus(user)" class="user-card__actions">
          <el-button v-if="canEditUsers" @click="openEdit(user)">编辑</el-button>
          <el-button v-if="canAssignUserRoles" @click="openRoles(user)">配置角色</el-button>
          <el-button v-if="mayChangeStatus(user)" :type="user.status === 'ACTIVE' ? 'danger' : 'success'" plain @click="toggleStatus(user)">{{ user.status === 'ACTIVE' ? '停用' : '启用' }}</el-button>
        </div>
      </article>
      <EmptyState v-if="!loading && !rows.length" description="暂无用户" compact />
    </div>
    </SectionCard>

    <el-dialog v-model="dialogVisible" :title="editingUser ? '编辑用户基本资料' : '创建用户'" class="user-dialog" width="min(560px, 92vw)" destroy-on-close>
      <el-form class="user-form" label-position="top" @submit.prevent="save">
        <el-row :gutter="16">
          <el-col :xs="24" :sm="12">
            <el-form-item label="用户名" required>
              <el-input v-model="form.username" :disabled="Boolean(editingUser)" autocomplete="username" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="显示名称" required>
              <el-input v-model="form.display_name" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="邮箱">
              <el-input v-model="form.email" type="email" autocomplete="email" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="手机号">
              <el-input v-model="form.mobile" type="tel" autocomplete="tel" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item v-if="!editingUser" label="初始密码" required>
          <el-input v-model="form.password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item v-if="!editingUser && canAssignUserRoles" label="初始角色">
          <el-checkbox-group v-model="form.role_ids" class="create-role-list">
            <el-checkbox
              v-for="role in roles"
              :key="role.id"
              :value="role.id"
              :disabled="isSuperAdminRole(role) && !operatorIsSuperAdmin"
            >
              {{ role.name }}
              <el-tag v-if="isSuperAdminRole(role)" type="danger" size="small">
                超级管理员 / 高风险
              </el-tag>
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <UserRoleAssignmentDrawer
      v-model="roleDrawerVisible"
      :user="roleUser"
      :roles="roles"
      :operator-is-super-admin="operatorIsSuperAdmin"
      :saving="roleSaving"
      @save="saveRoles"
    />
  </section>
</template>

<style scoped>
.create-role-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.create-role-list :deep(.el-checkbox) {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 42px;
  margin-right: 0;
  padding: 8px 10px;
  border: 1px solid var(--if-border);
  border-radius: 9px;
  background: var(--if-bg-surface);
  transition: border-color .16s ease, background-color .16s ease;
}
.create-role-list :deep(.el-checkbox:hover) { border-color: var(--if-brand-100); background: #f9fbff; }
.create-role-list :deep(.el-checkbox.is-checked) { border-color: var(--if-brand-100); background: var(--if-brand-50); }
.create-role-list :deep(.el-checkbox__label) {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
  padding-left: 9px;
  color: var(--if-text-1);
  font-size: 13px;
  line-height: 1.4;
  white-space: normal;
}
.create-role-list :deep(.el-checkbox__input) { flex: 0 0 auto; }
.create-role-list :deep(.el-tag) { margin: 0; }
.user-cards { display: grid; gap: 10px; padding: var(--if-space-4); }
.user-card { min-width: 0; padding: 14px; background: var(--if-bg-surface); border: 1px solid var(--if-border); border-radius: var(--if-radius); }
.user-card__head { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; margin-bottom: 12px; }
.user-card__head strong { display: block; font-size: 15px; }
.user-card__id { display: block; margin-top: 3px; color: var(--if-text-3); font-family: var(--if-font-mono); font-size: 12px; }
.user-card__details { display: grid; grid-template-columns: 42px minmax(0, 1fr); gap: 8px; margin-top: 6px; color: var(--if-text-2); font-size: 12px; }
.user-card__details span:last-child { color: var(--if-text-1); overflow-wrap: anywhere; }
.user-card__actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--if-border); }
.user-card__actions :deep(.el-button + .el-button) { margin-left: 0; }

@media (max-width: 767px) {
  .create-role-list { grid-template-columns: 1fr; }
}
</style>
