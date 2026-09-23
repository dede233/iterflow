<script setup lang="ts">
import type { RoleItem } from '@/types/system'

defineProps<{ role: RoleItem }>()

defineEmits<{
  edit: [role: RoleItem]
  delete: [role: RoleItem]
}>()
</script>

<template>
  <template v-if="!role.is_system">
    <el-button data-testid="edit-role" link type="primary" @click="$emit('edit', role)">编辑</el-button>
    <el-button data-testid="delete-role" link type="danger" @click="$emit('delete', role)">删除</el-button>
  </template>
</template>
