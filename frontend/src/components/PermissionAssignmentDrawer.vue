<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import {
  groupPermissions,
  setPermissionGroupSelection,
  type PermissionGroup,
} from '@/components/permissionAssignment'
import type { PermissionItem, RoleItem } from '@/types/system'

const props = defineProps<{
  modelValue: boolean
  role: RoleItem | null
  permissions: PermissionItem[]
  saving?: boolean
  readonly?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [visible: boolean]
  save: [permissionIds: number[]]
}>()

const selectedPermissionIds = ref<number[]>([])
const selectedPermissions = computed(() => new Set(selectedPermissionIds.value))
const expandedGroups = ref<string[]>([])
const sections = computed(() => groupPermissions(props.permissions))
const sectionHeadingId = useId()
const isReadonly = computed(() => Boolean(props.role?.is_system || props.readonly))
const drawerTitle = computed(() => {
  if (!props.role) return '权限配置'
  return `${isReadonly.value ? '查看权限' : '配置权限'} · ${props.role.name}`
})
const readonlyMessage = computed(() =>
  props.role?.is_system
    ? '系统角色为只读安全基线，以下权限仅供查看。'
    : '当前账号仅有角色查看权限，以下权限不可修改。',
)

watch(
  [() => props.modelValue, () => props.role],
  ([visible, role]) => {
    if (!visible || !role) return
    selectedPermissionIds.value = [...(role.permission_ids ?? [])]
    expandedGroups.value = sections.value.flatMap((section) => section.groups.map((group) => group.key))
  },
  { immediate: true },
)

function selectedCount(group: PermissionGroup): number {
  return group.permissions.filter((permission) => selectedPermissions.value.has(permission.id)).length
}

function groupSelected(group: PermissionGroup): boolean {
  return Boolean(group.permissions.length) && selectedCount(group) === group.permissions.length
}

function groupIndeterminate(group: PermissionGroup): boolean {
  const count = selectedCount(group)
  return count > 0 && count < group.permissions.length
}

function setGroupSelected(group: PermissionGroup, selected: boolean): void {
  selectedPermissionIds.value = setPermissionGroupSelection(
    selectedPermissionIds.value,
    group,
    selected,
  )
}

function close(): void {
  emit('update:modelValue', false)
}

function save(): void {
  emit('save', [...selectedPermissionIds.value].sort((left, right) => left - right))
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    :title="drawerTitle"
    size="min(760px, 100%)"
    destroy-on-close
    @close="close"
  >
    <template v-if="role">
      <el-alert
        v-if="isReadonly"
        :title="readonlyMessage"
        type="info"
        show-icon
        :closable="false"
      />
      <div class="summary" aria-live="polite">
        <span>已选择 {{ selectedPermissionIds.length }} / {{ permissions.length }} 项权限</span>
        <span v-if="!isReadonly" class="summary-tip">新增高风险权限时会要求二次确认</span>
      </div>

      <el-collapse v-model="expandedGroups" class="permission-groups">
        <component
          :is="section.nested ? 'section' : 'div'"
          v-for="(section, index) in sections"
          :key="section.key"
          :aria-labelledby="section.nested ? `${sectionHeadingId}-${index}` : undefined"
          :class="{ 'nested-section': section.nested }"
        >
          <h3 v-if="section.nested" :id="`${sectionHeadingId}-${index}`" class="section-title">{{ section.name }}</h3>
          <el-collapse-item v-for="group in section.groups" :key="group.key" :name="group.key">
            <template #title>
              <div class="group-title">
                <el-checkbox
                  :model-value="groupSelected(group)"
                  :indeterminate="groupIndeterminate(group)"
                  :disabled="isReadonly"
                  @click.stop
                  @keydown.space.enter.stop
                  @change="setGroupSelected(group, Boolean($event))"
                >
                  {{ group.name }}<span class="sr-only"> 全选</span>
                </el-checkbox>
                <span class="group-count">{{ selectedCount(group) }} / {{ group.permissions.length }}</span>
              </div>
            </template>

            <el-checkbox-group
              v-model="selectedPermissionIds"
              :disabled="isReadonly"
              :aria-label="`${group.name} 权限`"
              class="permission-list"
            >
              <el-checkbox
                v-for="permission in group.permissions"
                :key="permission.id"
                :value="permission.id"
                class="permission-option"
              >
                <span class="permission-label">
                  <span class="permission-name">{{ permission.name }}</span>
                  <code>{{ permission.code }}</code>
                  <el-tag v-if="permission.sensitive" type="danger" size="small" effect="light">高风险</el-tag>
                  <el-tag v-if="permission.deprecated" type="warning" size="small" effect="light">已废弃</el-tag>
                  <span v-if="permission.deprecated && permission.replacement_code" class="replacement-code">
                    替代权限：<code>{{ permission.replacement_code }}</code>
                  </span>
                </span>
              </el-checkbox>
            </el-checkbox-group>
          </el-collapse-item>
        </component>
      </el-collapse>
    </template>
    <el-empty v-else description="未选择角色" />

    <template #footer>
      <el-button @click="close">{{ isReadonly ? '关闭' : '取消' }}</el-button>
      <el-button v-if="role && !isReadonly" type="primary" :loading="saving" @click="save">
        保存权限
      </el-button>
    </template>
  </el-drawer>
</template>

<style scoped>
.summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 14px 0;
  color: var(--if-text-1);
  font-size: 14px;
  font-weight: 600;
}
.summary-tip { color: var(--if-warning-fg); font-size: 12px; font-weight: 500; }
.permission-groups { border-top: 1px solid var(--if-border); }
.nested-section { padding-left: var(--if-space-3); border-left: 2px solid var(--if-border); }
.nested-section :deep(.el-collapse-item__content) { padding-bottom: 0; }
.section-title { margin: 0; padding: 12px 0 4px; color: var(--if-text-1); font-size: 14px; font-weight: 600; }
.group-title { display: flex; flex: 1; align-items: center; justify-content: space-between; padding-right: 12px; }
.group-count { color: var(--if-text-3); font-size: 12px; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.permission-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 14px; padding: 6px 4px 14px; }
.permission-option { align-items: flex-start; height: auto; min-height: 48px; margin-right: 0; padding: 8px 10px; border: 1px solid var(--if-border); border-radius: var(--if-radius-sm); }
.permission-option :deep(.el-checkbox__label) { min-width: 0; white-space: normal; }
.permission-label { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }
.permission-name { color: var(--if-text-1); font-weight: 600; }
.permission-label code { width: 100%; color: var(--if-text-3); font-size: 12px; overflow-wrap: anywhere; }
.replacement-code { width: 100%; color: var(--if-warning-fg); font-size: 12px; }
.replacement-code code { display: inline; color: inherit; }
@media (max-width: 767px) {
  .summary { align-items: flex-start; flex-direction: column; }
  .permission-list { grid-template-columns: 1fr; }
}
</style>
