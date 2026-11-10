<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useScopedSearch } from '@/composables/useScopedSearch'
import { useScopedLookup } from '@/composables/useScopedLookup'
import { listFilterOptions, type FilterOptionKind } from '@/api/filterOptions'

const props = defineProps<{ modelValue: number | null; kind: FilterOptionKind; label: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: number | null] }>()
const auth = useAuthStore()
const allowed = computed(() => auth.hasPermission(props.kind === 'owner' ? 'rd.version.view' : 'rd.requirement.view'))
const identity = computed(() => `${props.kind}:${auth.user?.id}:${auth.accessToken}:${auth.permissionCodes.join(',')}`)
const selected = useScopedLookup(
  () => [props.modelValue, allowed.value, identity.value] as const,
  async id => {
    const result = await listFilterOptions(props.kind, '', 1, id)
    const option = result.items.find(option => option.id === id)
    if (!option) throw new Error('Selected filter is unavailable in the current scope')
    return option
  },
)
// Custom filtering keeps the dropdown usable before remote results arrive and
// lets asynchronously restored labels update; all searching still runs on the server.
const search = useScopedSearch(
  () => [allowed.value, identity.value] as const,
  async (keyword, page) => {
    const result = await listFilterOptions(props.kind, keyword, page)
    return { total: result.total, items: result.items.map(option => ({ id: option.id, code: '', title: option.label, status: '' })) }
  },
)
const options = computed(() => {
  const candidates = search.state.items.map(option => ({ id: option.id, label: option.title }))
  if (props.modelValue != null) candidates.unshift(selected.value ?? { id: props.modelValue, label: `已选择 ${props.label} #${props.modelValue}` })
  return [...new Map(candidates.map(option => [option.id, option])).values()]
})
function update(value: number | undefined | null | '') {
  emit('update:modelValue', typeof value === 'number' && Number.isSafeInteger(value) && value > 0 ? value : null)
}
</script>

<template>
  <el-select
    :model-value="modelValue"
    :aria-label="label"
    filterable clearable
    :loading="search.state.loading"
    :disabled="!allowed && modelValue == null"
    :placeholder="allowed ? `选择${label}（可搜索）` : `无权选择${label}`"
    :filter-method="search.search"
    :no-data-text="`暂无可见${label}`"
    @visible-change="$event ? search.open() : search.close()"
    @update:model-value="update"
  >
    <el-option v-for="option in options" :key="option.id" :value="option.id" :label="option.label" />
    <template v-if="search.state.error || search.state.total > 20" #footer>
      <div v-if="search.state.error" class="filter-options-message" role="alert">加载失败，请重试。<el-button link @click="search.retry">重试</el-button></div>
      <div v-else-if="search.state.total > 20" class="filter-options-pages">
        <el-button link :disabled="search.state.loading || search.state.page <= 1" @mousedown.prevent @click="search.paginate(search.state.page - 1)">上一页</el-button>
        <span>{{ search.state.page }} / {{ Math.ceil(search.state.total / 20) }}</span>
        <el-button link :disabled="search.state.loading || search.state.page * 20 >= search.state.total" @mousedown.prevent @click="search.paginate(search.state.page + 1)">下一页</el-button>
      </div>
    </template>
  </el-select>
</template>

<style scoped>
.filter-options-pages { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 12px; white-space: nowrap; }
.filter-options-pages :deep(.el-button + .el-button) { margin-left: 0; }
.filter-options-message { font-size: 12px; overflow-wrap: anywhere; }
</style>
