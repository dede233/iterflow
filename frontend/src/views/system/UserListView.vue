<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createUser, listUsers, sendUserEmailVerification, updateUser, updateUserRoles, updateUserStatus } from '@/api/users'
import { listRoles } from '@/api/roles'
import EmailSuggestionInput from '@/components/ui/EmailSuggestionInput.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useResponsive } from '@/composables/useResponsive'
import UserRoleAssignmentDrawer from '@/components/UserRoleAssignmentDrawer.vue'
import UserWecomBindingDialog from '@/components/UserWecomBindingDialog.vue'
import {
  buildUserBasicUpdatePayload,
  buildUserRoleUpdateRequest,
  canLoadRoleDefinitions,
  canOperatorChangeUserStatus,
  isAssignableRole,
  isCurrentUserSuperAdmin,
  isSuperAdminRole,
  statusConfirmationMessage,
} from '@/components/userRoleAssignment'
import { usePermission } from '@/composables/usePermission'
import { useAuthStore } from '@/stores/auth'
import { isRevisionConflict } from '@/types/revisionConflict'
import type { RoleItem, UserItem } from '@/types/system'

const { can } = usePermission()
const { isMobile } = useResponsive()
const auth = useAuthStore()
const pageSize = 20
const page = ref(1)
const total = ref(0)
const rows = ref<UserItem[]>([])
const roles = ref<RoleItem[]>([])
const loading = ref(false)
const failed = ref(false)
const dialogVisible = ref(false)
const editingUser = ref<UserItem | null>(null)
const customPassword = ref<string | null>(null)
const saving = ref(false)
const roleDrawerVisible = ref(false)
const roleUser = ref<UserItem | null>(null)
const roleSaving = ref(false)
const wecomUser = ref<UserItem | null>(null)
const wecomDialogVisible = ref(false)
const verificationSending = reactive(new Set<number>())
let loadSequence = 0
const form = reactive({
  username: '',
  display_name: '',
  email: '',
  mobile: '' as string | null,
  role_ids: [] as number[],
})
const initialPassword = computed({
  get() {
    const username = form.username.trim()
    return customPassword.value ?? (username ? `${username}123` : '')
  },
  set(password: string) {
    customPassword.value = password
  },
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
const canManageUserContacts = computed(() => hasAllScope.value && canEditUsers.value && operatorIsSuperAdmin.value)
const assignableRoles = computed(() => roles.value.filter(isAssignableRole))

type VerificationStatus = UserItem['email_verification_status']
const verificationLabels: Record<VerificationStatus, { label: string; type: string }> = {
  NO_EMAIL: { label: '未设置邮箱', type: 'info' },
  UNVERIFIED: { label: '未验证', type: 'info' },
  PENDING: { label: '待验证', type: 'warning' },
  FAILED: { label: '发送失败', type: 'danger' },
  VERIFIED: { label: '已验证', type: 'success' },
}

function verificationStatus(user: UserItem): VerificationStatus {
  return user.email ? user.email_verification_status ?? 'UNVERIFIED' : 'NO_EMAIL'
}

async function load(): Promise<void> {
  const sequence = ++loadSequence
  loading.value = true
  failed.value = false
  try {
    const [users, roleDefinitions] = await Promise.all([
      listUsers(page.value, pageSize),
      canReadRoleDefinitions.value ? listRoles() : [],
    ])
    if (sequence !== loadSequence) return
    rows.value = users.items
    total.value = users.total
    roles.value = roleDefinitions.filter((role) => role.enabled || role.assignable === false)
  } catch {
    if (sequence === loadSequence) failed.value = true
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

function changePage(nextPage: number): void {
  page.value = nextPage
  void load()
}

function resetForm(): void {
  Object.assign(form, { username: '', display_name: '', email: '', mobile: '', role_ids: [] })
  customPassword.value = null
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
    role_ids: [],
  })
  dialogVisible.value = true
}

function openRoles(user: UserItem): void {
  roleUser.value = user
  roleDrawerVisible.value = true
}

function openWecomBinding(user: UserItem): void {
  if (!canManageUserContacts.value || wecomUser.value) return
  wecomUser.value = user
  wecomDialogVisible.value = true
}

async function save(): Promise<void> {
  const username = form.username.trim()
  if (!editingUser.value && Array.from(initialPassword.value).length < 8) {
    ElMessage.warning(customPassword.value === null && username
      ? '默认密码不足 8 个字符，请手动设置至少 8 个字符的初始密码。'
      : '初始密码至少需要 8 个字符。')
    return
  }
  saving.value = true
  try {
    const email = form.email.trim() || null
    const mobile = form.mobile?.trim() || null
    if (!editingUser.value) {
      const created = await createUser({
        username,
        display_name: form.display_name.trim(),
        email,
        mobile,
        password: initialPassword.value,
        role_ids: form.role_ids,
      })
      if (created.verification_invitation === 'QUEUED') {
        ElMessage.success('用户已创建，验证邮件已排队。')
      } else if (created.verification_invitation === 'FAILED') {
        ElMessage.warning(canManageUserContacts.value
          ? '用户已创建，验证邮件入队失败。可在用户列表重新发送。'
          : '用户已创建，验证邮件入队失败。请联系超级管理员重新发送。')
      } else if (created.verification_invitation === 'SKIPPED' && email) {
        ElMessage.info('用户已创建，验证邮件未入队。')
      } else {
        ElMessage.success('用户已创建')
      }
      page.value = 1
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

function maySendVerification(user: UserItem): boolean {
  const status = verificationStatus(user)
  return canManageUserContacts.value && user.status === 'ACTIVE' && status !== 'NO_EMAIL' && status !== 'VERIFIED'
}

async function sendVerification(user: UserItem): Promise<void> {
  if (!maySendVerification(user) || verificationSending.has(user.id)) return
  verificationSending.add(user.id)
  try {
    await sendUserEmailVerification(user.id, { revision: user.revision })
    ElMessage.success('验证邮件已排队。')
    await load()
  } catch (error) {
    if (isRevisionConflict(error)) {
      ElMessage.warning('该账号已更新，请核对最新邮箱后重新发送验证邮件。')
      await load()
      return
    }
    const response = (error as { response?: { status?: number; data?: { message?: unknown } } })?.response
    if ([403, 409, 429].includes(response?.status ?? 0) && typeof response?.data?.message === 'string') {
      ElMessage.warning(response.data.message)
    } else {
      ElMessage.error('未能确认验证邮件入队，请核对验证状态后重试。')
    }
  } finally {
    verificationSending.delete(user.id)
  }
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
    <SectionCard v-else title="账号列表" :description="`共 ${total} 个账号`" :padded="false">
    <template #actions v-if="total > pageSize">
      <el-pagination
        class="user-pagination"
        aria-label="账号列表分页"
        layout="prev, pager, next"
        :pager-count="5"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        :disabled="loading"
        @update:current-page="changePage"
      />
    </template>
    <el-table v-if="!isMobile" v-loading="loading" :data="rows" row-key="id">
      <el-table-column prop="username" label="用户名" min-width="130" />
      <el-table-column prop="display_name" label="姓名" min-width="130" />
      <el-table-column label="邮箱" min-width="190">
        <template #default="{ row }">
          <div v-if="row.email" class="user-email">{{ row.email }}</div>
          <StatusTag :status="verificationStatus(row)" v-bind="verificationLabels[verificationStatus(row)]" size="sm" />
        </template>
      </el-table-column>
      <el-table-column label="角色" min-width="180">
        <template #default="scope">{{ roleNames(scope.row) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="scope">
          <StatusTag :status="scope.row.status" :label="scope.row.status === 'ACTIVE' ? '启用' : '停用'" />
        </template>
      </el-table-column>
      <el-table-column v-if="canEditUsers || canAssignUserRoles || canChangeUserStatus" label="操作" :width="canManageUserContacts ? 290 : 240" fixed="right">
        <template #default="scope">
          <div class="user-table-actions">
            <el-button v-if="canEditUsers" link type="primary" @click="openEdit(scope.row)">编辑</el-button>
            <el-button v-if="canAssignUserRoles" link type="primary" @click="openRoles(scope.row)">配置角色</el-button>
            <el-button v-if="mayChangeStatus(scope.row)" link :type="scope.row.status === 'ACTIVE' ? 'danger' : 'success'" @click="toggleStatus(scope.row)">
              {{ scope.row.status === 'ACTIVE' ? '停用' : '启用' }}
            </el-button>
            <el-button v-if="maySendVerification(scope.row)" link type="primary" :loading="verificationSending.has(scope.row.id)" @click="sendVerification(scope.row)">发送验证邮件</el-button>
            <el-button v-if="canManageUserContacts" link type="primary" @click="openWecomBinding(scope.row)">企业微信绑定</el-button>
          </div>
        </template>
      </el-table-column>
      <template #empty><EmptyState description="暂无用户" compact /></template>
    </el-table>
    <div v-else v-loading="loading" class="user-cards">
      <article v-for="user in rows" :key="user.id" class="user-card">
        <div class="user-card__head">
          <div class="user-card__identity">
            <strong>{{ user.display_name }}</strong>
            <span class="user-card__id">{{ user.username }}</span>
          </div>
          <StatusTag class="user-card__status" :status="user.status" :label="user.status === 'ACTIVE' ? '启用' : '停用'" size="sm" />
        </div>
        <div class="user-card__details"><span>角色</span><span>{{ roleNames(user) }}</span></div>
        <div class="user-card__details">
          <span>邮箱</span>
          <div>
            <div v-if="user.email" class="user-email">{{ user.email }}</div>
            <StatusTag :status="verificationStatus(user)" v-bind="verificationLabels[verificationStatus(user)]" size="sm" />
          </div>
        </div>
        <div v-if="canEditUsers || canAssignUserRoles || mayChangeStatus(user)" class="user-card__actions">
          <el-button v-if="canEditUsers" @click="openEdit(user)">编辑</el-button>
          <el-button v-if="canAssignUserRoles" @click="openRoles(user)">配置角色</el-button>
          <el-button v-if="mayChangeStatus(user)" :type="user.status === 'ACTIVE' ? 'danger' : 'success'" plain @click="toggleStatus(user)">{{ user.status === 'ACTIVE' ? '停用' : '启用' }}</el-button>
          <el-button v-if="maySendVerification(user)" type="primary" plain :loading="verificationSending.has(user.id)" @click="sendVerification(user)">发送验证邮件</el-button>
          <el-button v-if="canManageUserContacts" @click="openWecomBinding(user)">企业微信绑定</el-button>
        </div>
      </article>
      <EmptyState v-if="!loading && !rows.length" description="暂无用户" compact />
    </div>
    </SectionCard>

    <el-dialog v-model="dialogVisible" :title="editingUser ? '编辑用户基本资料' : '创建用户'" class="user-dialog" width="min(560px, 92vw)" destroy-on-close @closed="resetForm">
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
            <el-form-item label="邮箱" for="user-account-email">
              <EmailSuggestionInput id="user-account-email" v-model="form.email" :maxlength="255" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="手机号">
              <el-input v-model="form.mobile" type="tel" autocomplete="tel" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item v-if="!editingUser" label="初始密码" required>
          <el-input v-model="initialPassword" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item v-if="!editingUser && canAssignUserRoles" label="初始角色">
          <el-checkbox-group v-model="form.role_ids" class="create-role-list">
            <el-checkbox
              v-for="role in assignableRoles"
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
    <UserWecomBindingDialog
      v-if="canManageUserContacts && wecomUser"
      v-model="wecomDialogVisible"
      :user="wecomUser"
      @closed="wecomUser = null"
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
.user-pagination { margin-top: 0; }
.user-email { margin-bottom: 2px; overflow-wrap: anywhere; }
.user-table-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 12px; }
.user-table-actions :deep(.el-button + .el-button) { margin-left: 0; }
.user-cards { display: grid; gap: 10px; padding: var(--if-space-4); }
.user-card { min-width: 0; padding: 14px; background: var(--if-bg-surface); border: 1px solid var(--if-border); border-radius: var(--if-radius); }
.user-card__head { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; margin-bottom: 12px; }
.user-card__identity { min-width: 0; overflow-wrap: anywhere; }
.user-card__status { flex-shrink: 0; }
.user-card__head strong { display: block; font-size: 15px; }
.user-card__id { display: block; margin-top: 3px; color: var(--if-text-3); font-family: var(--if-font-mono); font-size: 12px; }
.user-card__details { display: grid; grid-template-columns: 42px minmax(0, 1fr); gap: 8px; margin-top: 6px; color: var(--if-text-2); font-size: 12px; }
.user-card__details span:last-child { color: var(--if-text-1); overflow-wrap: anywhere; }
.user-card__actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--if-border); }
.user-card__actions :deep(.el-button + .el-button) { margin-left: 0; }

@media (max-width: 767px) {
  .create-role-list { grid-template-columns: 1fr; }
  .user-pagination :deep(button),
  .user-pagination :deep(.el-pager li) { min-height: 44px; min-width: 36px; }
  .user-card__actions :deep(.el-button) { min-height: 44px; }
}
</style>
