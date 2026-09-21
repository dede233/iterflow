<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createRole, listPermissions, listRoles, updateRole, updateRolePermissions } from '@/api/roles'
import { usePermission } from '@/composables/usePermission'
import type { PermissionItem, RoleItem } from '@/types/system'

const { can } = usePermission()
const rows = ref<RoleItem[]>([])
const permissions = ref<PermissionItem[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingRole = ref<RoleItem | null>(null)
const saving = ref(false)
const form = reactive({
  code: '',
  name: '',
  data_scope: 'SELF' as 'SELF' | 'ALL',
  enabled: true,
  permission_ids: [] as number[],
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
  Object.assign(form, { code: '', name: '', data_scope: 'SELF', enabled: true, permission_ids: [] })
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
    permission_ids: [...role.permission_ids],
  })
  dialogVisible.value = true
}

async function save(): Promise<void> {
  saving.value = true
  try {
    if (!editingRole.value) {
      await createRole({
        code: form.code.trim(),
        name: form.name.trim(),
        data_scope: form.data_scope,
        permission_ids: form.permission_ids,
      })
      ElMessage.success('角色已创建')
    } else {
      let role = await updateRole(editingRole.value.id, {
        code: form.code.trim(),
        name: form.name.trim(),
        data_scope: form.data_scope,
        enabled: form.enabled,
        revision: editingRole.value.revision,
      })
      const previousPermissions = [...editingRole.value.permission_ids].sort().join(',')
      const nextPermissions = [...form.permission_ids].sort().join(',')
      if (previousPermissions !== nextPermissions) {
        role = await updateRolePermissions(role.id, form.permission_ids, role.revision)
      }
      ElMessage.success('角色已更新')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
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
      <el-button v-if="can('sys.role.edit')" type="primary" @click="openCreate">创建角色</el-button>
    </div>
    <el-alert title="角色与权限配置建议在 PC 端完成" type="info" show-icon :closable="false" />
    <el-table v-loading="loading" :data="rows" row-key="id" class="role-table">
      <el-table-column prop="code" label="编码" min-width="180" />
      <el-table-column prop="name" label="角色" min-width="140" />
      <el-table-column prop="data_scope" label="数据范围" width="110" />
      <el-table-column label="权限" min-width="280">
        <template #default="scope">{{ permissionNames(scope.row) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="scope"><el-tag :type="scope.row.enabled ? 'success' : 'info'">{{ scope.row.enabled ? '启用' : '停用' }}</el-tag></template>
      </el-table-column>
      <el-table-column v-if="can('sys.role.edit')" label="操作" width="80" fixed="right">
        <template #default="scope"><el-button link type="primary" @click="openEdit(scope.row)">编辑</el-button></template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingRole ? '编辑角色' : '创建角色'" width="min(680px, 94vw)" destroy-on-close>
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
        <el-form-item label="权限">
          <el-checkbox-group v-model="form.permission_ids" class="permissions">
            <el-checkbox v-for="permission in permissions" :key="permission.id" :value="permission.id">
              {{ permission.name }}（{{ permission.code }}）
            </el-checkbox>
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
.role-table { margin-top: 12px; }
.permissions { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px 16px; width: 100%; }
.permissions :deep(.el-checkbox) { height: auto; min-height: 28px; margin-right: 0; white-space: normal; }
@media (max-width: 767px) { .head { align-items: center; } }
</style>
