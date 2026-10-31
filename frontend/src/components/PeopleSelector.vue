<script setup lang="ts">
import { onScopeDispose, ref, watch } from 'vue'
import { listPeople, type Person } from '@/api/collaboration'
import { useAuthStore } from '@/stores/auth'
const props = defineProps<{ modelValue: number[]; kind: 'feedback' | 'requirement'; feedbackId?: number; selected?: Person[]; multiple?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [number[]] }>()
const auth = useAuthStore()
const options = ref<Person[]>([])
const loading = ref(false)
const failed = ref(false)
const keyword = ref('')
const page = ref(1)
const total = ref(0)
let sequence = 0
async function search(value = '', next = false) {
  keyword.value = value
  page.value = next ? page.value + 1 : 1
  const request = ++sequence
  loading.value = true
  failed.value = false
  try {
    const result = await listPeople(props.kind, value, page.value, props.feedbackId)
    if (request !== sequence) return
    options.value = next ? [...options.value, ...result.items] : result.items
    total.value = result.total
  } catch { if (request === sequence) failed.value = true }
  finally { if (request === sequence) loading.value = false }
}
watch(() => [props.kind, props.feedbackId, auth.user?.id, auth.accessToken, auth.permissionCodes.join(',')], () => {
  sequence++; options.value = []; total.value = 0; loading.value = false
}, { flush: 'sync' })
onScopeDispose(() => { sequence++ })
function available() {
  return [...new Map([...(props.selected ?? []), ...options.value].map(p => [p.id, p])).values()]
}
</script>
<template>
  <el-select :model-value="multiple ? modelValue : modelValue[0]" :multiple="multiple" filterable remote clearable :remote-method="search" :loading="loading" placeholder="搜索人员" style="width:100%" @visible-change="$event && search()" @update:model-value="emit('update:modelValue', multiple ? $event : ($event ? [$event] : []))">
    <el-option v-for="person in available()" :key="person.id" :label="person.display_name" :value="person.id" />
    <template #footer>
      <span v-if="failed">人员加载失败 <el-button link @click="search(keyword)">重试</el-button></span>
      <el-button v-else-if="options.length < total" link :disabled="loading" @click="search(keyword, true)">加载更多</el-button>
      <span v-else-if="!options.length && !loading">暂无符合权限范围的人员</span>
    </template>
  </el-select>
</template>
