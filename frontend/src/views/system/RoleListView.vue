<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createRole, deleteRole, listPermissions, listRoles, updateRole, updateRolePermissions } from '@/api/roles'
import PermissionAssignmentDrawer from '@/components/PermissionAssignmentDrawer.vue'
import RoleActions from '@/components/RoleActions.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import StatusTag from '@/components/StatusTag.vue'
import {
  buildPermissionUpdateRequest,
  buildRoleBasicUpdatePayload,
  confirmAddedSensitivePermissions,
} from '@/components/permissionAssignment'
import { usePermission } from '@/composables/usePermission'
import { useResponsive } from '@/composables/useResponsive'
import type { PermissionItem, RoleItem } from '@/types/system'

const { can } = usePermission()
const { isMobile } = useResponsive()
const canManage = computed(() => can('sys.role.manage'))
const rows = ref<RoleItem[]>([])
const permissions = ref<PermissionItem[]>([])
const loading = ref(false)
const failed = ref(false)
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
  failed.value = false
  try {
    const [roles, availablePermissions] = await Promise.all([listRoles(), listPermissions()])
    rows.value = roles
    permissions.value = availablePermissions
  } catch {
    failed.value = true
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
    role.permission_ids ?? [],
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
      { permission_ids: request.permissionIds, revision: request.revision },
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
  const labels = (role.permission_ids ?? [])
    .map((permissionId) => permissions.value.find((permission) => permission.id === permissionId)?.name)
    .filter((name): name is string => Boolean(name))
  return labels.length ? labels.join('、') : '无权限'
}

onMounted(load)
</script>

<template>
  <section class="page">
    <PageHeader title="角色与权限" description="配置角色的数据范围和操作权限。" eyebrow="系统治理">
      <template #actions><el-button v-if="canManage" type="primary" @click="openCreate">创建角色</el-button></template>
    </PageHeader>
    <el-alert v-if="isMobile" class="mobile-notice" title="复杂权限配置建议在 PC 端完成" type="info" show-icon :closable="false" />
    <ErrorState v-if="failed" title="角色列表加载失败" description="请检查网络后重试。" retry-label="重新加载" @retry="load" />
    <SectionCard v-else title="角色清单" :description="`共 ${rows.length} 个角色 · TEAM 数据范围暂不可配置`" :padded="false">
    <el-table v-if="!isMobile" v-loading="loading" :data="rows" row-key="id" class="role-table">
      <el-table-column prop="code" label="编码" min-width="150" />
      <el-table-column prop="name" label="角色" min-width="120" />
      <el-table-column label="类型" width="100">
        <template #default="scope"><StatusTag :status="scope.row.is_system ? 'SYSTEM' : 'CUSTOM'" :label="scope.row.is_system ? '系统角色' : '自定义角色'" :type="scope.row.is_system ? 'info' : 'success'" /></template>
      </el-table-column>
      <el-table-column prop="data_scope" label="数据范围" width="100" />
      <el-table-column label="权限" min-width="180" show-overflow-tooltip>
        <template #default="scope">{{ permissionNames(scope.row) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="scope"><StatusTag :status="scope.row.enabled ? 'ENABLED' : 'DISABLED'" :label="scope.row.enabled ? '启用' : '停用'" /></template>
      </el-table-column>
      <el-table-column label="操作" width="210" fixed="right">
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
    <div v-else v-loading="loading" class="role-cards">
      <article v-for="role in rows" :key="role.id" class="role-card">
        <div class="role-card__head"><div><strong>{{ role.name }}</strong><span class="role-card__code">{{ role.code }}</span></div><StatusTag :status="role.enabled ? 'ENABLED' : 'DISABLED'" :label="role.enabled ? '启用' : '停用'" size="sm" /></div>
        <div class="role-card__badges"><StatusTag :status="role.is_system ? 'SYSTEM' : 'CUSTOM'" :label="role.is_system ? '系统角色' : '自定义角色'" :type="role.is_system ? 'info' : 'success'" size="sm" /><span>数据范围：{{ role.data_scope }}</span></div>
        <p class="role-card__permissions">{{ permissionNames(role) }}</p>
        <div class="role-card__actions"><RoleActions :role="role" :can-manage="canManage" @edit="openEdit" @permissions="openPermissions" @delete="remove" /></div>
      </article>
      <EmptyState v-if="!loading && !rows.length" description="暂无角色" compact />
    </div>
    </SectionCard>

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
.mobile-notice { margin-bottom: var(--if-space-4); }
.role-cards { display: grid; gap: 10px; padding: var(--if-space-4); }
.role-card { min-width: 0; padding: 14px; background: var(--if-bg-surface); border: 1px solid var(--if-border); border-radius: var(--if-radius); }
.role-card__head { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.role-card__head strong { display: block; font-size: 15px; }
.role-card__code { display: block; margin-top: 3px; color: var(--if-text-3); font-family: var(--if-font-mono); font-size: 12px; overflow-wrap: anywhere; }
.role-card__badges { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 12px; color: var(--if-text-2); font-size: 12px; }
.role-card__permissions { display: -webkit-box; margin: 12px 0 0; overflow: hidden; color: var(--if-text-2); font-size: 12px; line-height: 1.5; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow-wrap: anywhere; }
.role-card__actions { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--if-border); }
</style>
