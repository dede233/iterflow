<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { isSuperAdminRole } from '@/components/userRoleAssignment'
import type { RoleItem, UserItem } from '@/types/system'

const props = defineProps<{
  modelValue: boolean
  user: UserItem | null
  roles: RoleItem[]
  operatorIsSuperAdmin: boolean
  saving?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [visible: boolean]
  save: [roleIds: number[]]
}>()

const selectedRoleIds = ref<number[]>([])
const enabledRoles = computed(() => props.roles.filter((role) => role.enabled))

watch(
  [() => props.modelValue, () => props.user],
  ([visible, user]) => {
    if (visible && user) selectedRoleIds.value = [...user.role_ids]
  },
  { immediate: true },
)

function close(): void {
  emit('update:modelValue', false)
}

function save(): void {
  emit('save', [...selectedRoleIds.value].sort((left, right) => left - right))
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    :title="user ? `配置角色 · ${user.display_name}` : '配置角色'"
    size="min(640px, 100%)"
    destroy-on-close
    @close="close"
  >
    <template v-if="user">
      <el-alert
        v-if="!operatorIsSuperAdmin"
        title="只有超级管理员可以授予或撤销超级管理员角色。"
        type="warning"
        show-icon
        :closable="false"
      />
      <div class="assignment-summary" aria-live="polite">
        已选择 {{ selectedRoleIds.length }} / {{ enabledRoles.length }} 个角色
      </div>
      <el-checkbox-group v-model="selectedRoleIds" class="role-list" aria-label="用户角色">
        <el-checkbox
          v-for="role in enabledRoles"
          :key="role.id"
          :value="role.id"
          :disabled="isSuperAdminRole(role) && !operatorIsSuperAdmin"
          class="role-option"
        >
          <span class="role-label">
            <span>{{ role.name }}</span>
            <code>{{ role.code }}</code>
            <el-tag v-if="isSuperAdminRole(role)" type="danger" size="small" effect="light">
              超级管理员 / 高风险
            </el-tag>
          </span>
        </el-checkbox>
      </el-checkbox-group>
    </template>
    <el-empty v-else description="未选择用户" />

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button v-if="user" type="primary" :loading="saving" @click="save">
        保存角色
      </el-button>
    </template>
  </el-drawer>
</template>

<style scoped>
.assignment-summary {
  margin: 16px 0 12px;
  color: #334155;
  font-size: 14px;
  font-weight: 600;
}
.role-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.role-option {
  align-items: flex-start;
  height: auto;
  min-height: 64px;
  margin-right: 0;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}
.role-option :deep(.el-checkbox__label) { min-width: 0; white-space: normal; }
.role-label { display: flex; flex-wrap: wrap; align-items: center; gap: 5px 8px; }
.role-label code { width: 100%; color: #64748b; font-size: 12px; }
@media (max-width: 767px) {
  .role-list { grid-template-columns: 1fr; }
  .role-option { min-height: 56px; }
}
</style>
