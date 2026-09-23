<script setup lang="ts">
import type { RoleItem } from '@/types/system'

defineProps<{
  role: RoleItem
  canManage: boolean
}>()

defineEmits<{
  edit: [role: RoleItem]
  permissions: [role: RoleItem]
  delete: [role: RoleItem]
}>()
</script>

<template>
  <template v-if="role.is_system || !canManage">
    <el-button data-testid="view-permissions" link type="primary" @click="$emit('permissions', role)">
      查看权限
    </el-button>
  </template>
  <template v-else>
    <el-button data-testid="edit-role" link type="primary" @click="$emit('edit', role)">编辑</el-button>
    <el-button data-testid="configure-permissions" link type="primary" @click="$emit('permissions', role)">
      配置权限
    </el-button>
    <el-button data-testid="delete-role" link type="danger" @click="$emit('delete', role)">删除</el-button>
  </template>
</template>
