<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createUser, listUsers, updateUser, updateUserRoles, updateUserStatus } from '@/api/users'
import { listRoles } from '@/api/roles'
import { usePermission } from '@/composables/usePermission'
import { useAuthStore } from '@/stores/auth'
import type { RoleItem, UserItem } from '@/types/system'

const { can } = usePermission()
const auth = useAuthStore()
const rows = ref<UserItem[]>([])
const roles = ref<RoleItem[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingUser = ref<UserItem | null>(null)
const saving = ref(false)
const form = reactive({
  username: '',
  display_name: '',
  email: '' as string | null,
  mobile: '' as string | null,
  password: '',
  role_ids: [] as number[],
})
const canReadRoleDefinitions = computed(
  () => auth.user?.data_scope === 'ALL' && can('sys.role.view'),
)
const hasAllScope = computed(() => auth.user?.data_scope === 'ALL')
const canAssignUserRoles = computed(() => hasAllScope.value && can('sys.user.role.assign'))
const canCreateUsers = computed(() => hasAllScope.value && can('sys.user.create') && canAssignUserRoles.value)
const canEditUsers = computed(() => can('sys.user.edit'))
const canChangeUserStatus = computed(() => hasAllScope.value && can('sys.user.status'))

async function load(): Promise<void> {
  loading.value = true
  try {
    const users = await listUsers()
    rows.value = users.items
    roles.value = canReadRoleDefinitions.value
      ? (await listRoles()).filter((role) => role.enabled)
      : []
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
    role_ids: [...user.role_ids],
  })
  dialogVisible.value = true
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
      let updated = await updateUser(editingUser.value.id, {
        display_name: form.display_name.trim(),
        email,
        mobile,
        revision: editingUser.value.revision,
      })
      const originalRoleIds = [...editingUser.value.role_ids].sort().join(',')
      const nextRoleIds = [...form.role_ids].sort().join(',')
      if (canAssignUserRoles.value && originalRoleIds !== nextRoleIds) {
        updated = await updateUserRoles(updated.id, form.role_ids, updated.revision)
      }
      ElMessage.success('用户已更新')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function toggleStatus(user: UserItem): Promise<void> {
  const status = user.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE'
  const action = status === 'ACTIVE' ? '启用' : '停用'
  await ElMessageBox.confirm(`确定要${action}用户“${user.display_name}”吗？`, `${action}用户`, {
    confirmButtonText: action,
    cancelButtonText: '取消',
    type: 'warning',
  })
  await updateUserStatus(user.id, status, user.revision)
  ElMessage.success(`用户已${action}`)
  await load()
}

function roleNames(user: UserItem): string {
  if (!canReadRoleDefinitions.value) {
    return user.role_ids.length ? `已分配 ${user.role_ids.length} 个角色` : '未分配'
  }
  const labels = user.role_ids
    .map((roleId) => roles.value.find((role) => role.id === roleId)?.name)
    .filter((name): name is string => Boolean(name))
  return labels.length ? labels.join('、') : '未分配'
}

onMounted(load)
</script>

<template>
  <section class="page">
    <div class="head">
      <div>
        <h1 class="page-title">用户管理</h1>
        <p class="hint">账号密码不会在列表或接口响应中展示。</p>
      </div>
      <el-button v-if="canCreateUsers" type="primary" @click="openCreate">创建用户</el-button>
    </div>

    <el-table v-loading="loading" :data="rows" row-key="id">
      <el-table-column prop="username" label="用户名" min-width="130" />
      <el-table-column prop="display_name" label="姓名" min-width="130" />
      <el-table-column prop="email" label="邮箱" min-width="180" />
      <el-table-column label="角色" min-width="180">
        <template #default="scope">{{ roleNames(scope.row) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="scope">
          <el-tag :type="scope.row.status === 'ACTIVE' ? 'success' : 'info'">{{ scope.row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="canEditUsers || canChangeUserStatus" label="操作" width="180" fixed="right">
        <template #default="scope">
          <el-button v-if="canEditUsers" link type="primary" @click="openEdit(scope.row)">编辑</el-button>
          <el-button v-if="canChangeUserStatus" link :type="scope.row.status === 'ACTIVE' ? 'danger' : 'success'" @click="toggleStatus(scope.row)">
            {{ scope.row.status === 'ACTIVE' ? '停用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingUser ? '编辑用户' : '创建用户'" width="min(560px, 92vw)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="save">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" :disabled="Boolean(editingUser)" autocomplete="username" />
        </el-form-item>
        <el-form-item label="显示名称" required>
          <el-input v-model="form.display_name" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" type="email" autocomplete="email" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="form.mobile" type="tel" autocomplete="tel" />
        </el-form-item>
        <el-form-item v-if="!editingUser" label="初始密码" required>
          <el-input v-model="form.password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item v-if="canAssignUserRoles" label="角色">
          <el-checkbox-group v-model="form.role_ids">
            <el-checkbox v-for="role in roles" :key="role.id" :value="role.id">{{ role.name }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.hint { margin: -8px 0 16px; color: #64748b; font-size: 13px; }
@media (max-width: 767px) { .head { align-items: center; } }
</style>
