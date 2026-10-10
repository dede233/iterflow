<script setup lang="ts">
import { computed, ref } from 'vue'
import { listAssigneeOptions, type AssigneeKind, type AssigneeOption } from '@/api/requirementCollaboration'
const props = defineProps<{ modelValue: number | number[] | null; kind: AssigneeKind; selected: AssigneeOption[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: number | number[] | null] }>()
const options = ref<AssigneeOption[]>([])
const loading = ref(false)
const failed = ref(false)
const keyword = ref('')
const page = ref(1)
const hasMore = ref(false)
let request = 0
const displayed = computed(() => Array.from(new Map([...props.selected, ...options.value].map(o => [o.user_id, o])).values()))
async function search(value: string, more = false): Promise<void> {
  const generation = ++request
  const nextPage = more ? page.value + 1 : 1
  keyword.value = value
  loading.value = true
  failed.value = false
  try {
    const result = await listAssigneeOptions(props.kind, value, nextPage)
    if (generation !== request) return
    options.value = more ? [...options.value, ...result.items] : result.items
    page.value = nextPage
    hasMore.value = nextPage * result.page_size < result.total
  } catch {
    if (generation === request) failed.value = true
  } finally {
    if (generation === request) loading.value = false
  }
}
function onOpen(open: boolean): void { if (open) void search('') }
</script>
<template>
  <div class="assignee-select">
    <el-select :model-value="modelValue" :multiple="kind !== 'OWNER'" clearable filterable remote :remote-method="search" :loading="loading" placeholder="输入姓名查找" @visible-change="onOpen" @update:model-value="emit('update:modelValue', kind === 'OWNER' && ($event === '' || $event === undefined) ? null : $event)">
      <el-option v-for="person in displayed" :key="person.user_id" :label="person.display_name" :value="person.user_id" />
    </el-select>
    <el-button v-if="hasMore && !failed" link :loading="loading" @click="search(keyword, true)">加载更多候选人员</el-button>
    <el-button v-if="failed" link type="danger" @click="search(keyword)">人员加载失败，重试</el-button>
  </div>
</template>
<style scoped>
.assignee-select, .assignee-select :deep(.el-select) { width: 100%; min-width: 0; }
</style>
