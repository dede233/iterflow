<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createRole, deleteRole, listPermissions, listRoles, updateRole, updateRolePermissions } from '@/api/roles'
import PermissionAssignmentDrawer from '@/components/PermissionAssignmentDrawer.vue'
import RoleActions from '@/components/RoleActions.vue'
import {
  buildPermissionUpdateRequest,
  buildRoleBasicUpdatePayload,
  confirmAddedSensitivePermissions,
} from '@/components/permissionAssignment'
import { usePermission } from '@/composables/usePermission'
import type { PermissionItem, RoleItem } from '@/types/system'

const { can } = usePermission()
const canManage = computed(() => can('sys.role.manage'))
const rows = ref<RoleItem[]>([])
const permissions = ref<PermissionItem[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingRole = ref<RoleItem | null>(null)
const saving = ref(false)
const permissionDrawerVisible = ref(false)
const permissionRole = ref<RoleItem | null>(null)
const permissionSaving = ref(false)
const form = reactive({
  code: '',
  name: '',
  data_scope: 'SELF' as 'SELF' | 'ALL',
  enabled: true,
})

async function load(): Promise<void> {
  loading.value = true
  try {
    const [roles, availablePermissions] = await Promise.all([listRoles(), listPermissions()])
    rows.value = roles
    permissions.value = availablePermissions
  } finally {
    loading.value = false
  }
}

function resetForm(): void {
  Object.assign(form, { code: '', name: '', data_scope: 'SELF', enabled: true })
}

function openCreate(): void {
  editingRole.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(role: RoleItem): void {
  editingRole.value = role
  Object.assign(form, {
    code: role.code,
    name: role.name,
    data_scope: role.data_scope === 'ALL' ? 'ALL' : 'SELF',
    enabled: role.enabled,
  })
  dialogVisible.value = true
}

function openPermissions(role: RoleItem): void {
  permissionRole.value = role
  permissionDrawerVisible.value = true
}

async function save(): Promise<void> {
  saving.value = true
  try {
    if (!editingRole.value) {
      const created = await createRole({
        code: form.code.trim(),
        name: form.name.trim(),
        data_scope: form.data_scope,
        permission_ids: [],
      })
      ElMessage.success('角色已创建，请继续配置权限')
      dialogVisible.value = false
      await load()
      openPermissions(rows.value.find((role) => role.id === created.id) ?? created)
    } else {
      await updateRole(
        editingRole.value.id,
        buildRoleBasicUpdatePayload(form, editingRole.value.revision),
      )
      ElMessage.success('角色已更新')
      dialogVisible.value = false
      await load()
    }
  } finally {
    saving.value = false
  }
}

async function savePermissions(permissionIds: number[]): Promise<void> {
  const role = permissionRole.value
  if (!role || role.is_system || !canManage.value) return
  const confirmed = await confirmAddedSensitivePermissions(
    role.permission_ids,
    permissionIds,
    permissions.value,
    (message) =>
      ElMessageBox.confirm(message, '确认高风险权限', {
        type: 'warning',
        confirmButtonText: '确认授权',
        cancelButtonText: '取消',
      }),
  )
  if (!confirmed) return

  permissionSaving.value = true
  try {
    const request = buildPermissionUpdateRequest(role, permissionIds)
    const updated = await updateRolePermissions(
      request.roleId,
      request.permissionIds,
      request.revision,
    )
    permissionRole.value = updated
    permissionDrawerVisible.value = false
    ElMessage.success('角色权限已更新')
    await load()
  } finally {
    permissionSaving.value = false
  }
}

async function remove(role: RoleItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除自定义角色“${role.name}”吗？此操作不可撤销。`, '删除角色', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  await deleteRole(role.id)
  ElMessage.success('角色已删除')
  await load()
}

function permissionNames(role: RoleItem): string {
  const labels = role.permission_ids
    .map((permissionId) => permissions.value.find((permission) => permission.id === permissionId)?.name)
    .filter((name): name is string => Boolean(name))
  return labels.length ? labels.join('、') : '无权限'
}

onMounted(load)
</script>

<template>
  <section class="page">
    <div class="head">
      <div>
        <h1 class="page-title">角色与权限</h1>
        <p class="hint">TEAM 数据范围为保留值，当前版本不可配置。</p>
      </div>
      <el-button v-if="canManage" type="primary" @click="openCreate">创建角色</el-button>
    </div>
    <el-alert title="角色与权限配置建议在 PC 端完成" type="info" show-icon :closable="false" />
    <el-table v-loading="loading" :data="rows" row-key="id" class="role-table">
      <el-table-column prop="code" label="编码" min-width="180" />
      <el-table-column prop="name" label="角色" min-width="140" />
      <el-table-column label="类型" width="100">
        <template #default="scope"><el-tag :type="scope.row.is_system ? 'info' : 'success'">{{ scope.row.is_system ? '系统角色' : '自定义角色' }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="data_scope" label="数据范围" width="110" />
      <el-table-column label="权限" min-width="280">
        <template #default="scope">{{ permissionNames(scope.row) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="scope"><el-tag :type="scope.row.enabled ? 'success' : 'info'">{{ scope.row.enabled ? '启用' : '停用' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="scope">
          <RoleActions
            :role="scope.row"
            :can-manage="canManage"
            @edit="openEdit"
            @permissions="openPermissions"
            @delete="remove"
          />
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingRole ? '编辑角色基本信息' : '创建角色'" width="min(680px, 94vw)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="save">
        <el-row :gutter="16">
          <el-col :xs="24" :sm="12"><el-form-item label="编码" required><el-input v-model="form.code" /></el-form-item></el-col>
          <el-col :xs="24" :sm="12"><el-form-item label="角色名称" required><el-input v-model="form.name" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="数据范围">
          <el-radio-group v-model="form.data_scope">
            <el-radio value="SELF">仅本人</el-radio>
            <el-radio value="ALL">全部数据</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="editingRole" label="状态"><el-switch v-model="form.enabled" active-text="启用" inactive-text="停用" /></el-form-item>
        <el-alert
          v-if="!editingRole"
          title="创建成功后将打开独立权限配置，创建与后续授权为两个明确步骤。"
          type="info"
          show-icon
          :closable="false"
        />
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <PermissionAssignmentDrawer
      v-model="permissionDrawerVisible"
      :role="permissionRole"
      :permissions="permissions"
      :saving="permissionSaving"
      :readonly="!canManage"
      @save="savePermissions"
    />
  </section>
</template>

<style scoped>
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.hint { margin: -8px 0 16px; color: #64748b; font-size: 13px; }
.role-table { margin-top: 12px; }
@media (max-width: 767px) { .head { align-items: center; } }
</style>
