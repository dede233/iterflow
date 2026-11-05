<script setup lang="ts">
import { computed, onScopeDispose, reactive, ref, watch } from 'vue'
import { api } from '@/api/client'
import { listRequirements } from '@/api/requirements'
import { createRequestId } from '@/utils/requestId'
import { useAuthStore } from '@/stores/auth'
import { REQUIREMENT_STATUSES, REQUIREMENT_PRIORITIES, requirementStatusLabel } from '@/constants/requirement'
import type { Requirement, RequirementListParams } from '@/types/domain'
const props = defineProps<{ versionId: number; revision: number; systemId?: number | null }>()
const emit = defineEmits<{ updated: []; cancel: [] }>()
const auth = useAuthStore()
const rows = ref<Requirement[]>([])
const selected = ref<Map<number, Requirement>>(new Map())
const filters = reactive({ keyword: '', status: '' as RequirementListParams['status'], priority: '' as RequirementListParams['priority'] })
const page = ref(1), total = ref(0), loading = ref(false), saving = ref(false)
const failed = ref(false), error = ref('')
const problems = ref<{ requirement_id: number; reason: string }[]>([])
// Both version and requirement revisions belong to the user's original selection.
const versionRevision = props.revision
const requestId = createRequestId()
let sequence = 0
const identity = computed(() => `${auth.user?.id}:${auth.accessToken}:${auth.permissionCodes.join(',')}`)
function disabledReason(row: Requirement) {
  if (!props.systemId) return '请先补齐版本的业务系统'
  if (!row.system_id || row.system_id !== props.systemId) return '需求与版本的业务系统不一致或未指定'
  if (row.current_version_id) return row.current_version_id === props.versionId ? '已在本版本' : '已有其他版本，请使用迁移'
  return ['ONLINE', 'CANCELED'].includes(row.status) ? '终态需求不可添加' : ''
}
async function load() {
  const request = ++sequence; failed.value = false; loading.value = true; rows.value = []
  if (!auth.hasPermission('rd.requirement.view')) { loading.value = false; return }
  try {
    const result = await listRequirements({ system_id: props.systemId || undefined, page: page.value, page_size: 20, keyword: filters.keyword || undefined, status: filters.status || undefined, priority: filters.priority || undefined })
    if (request !== sequence) return
    rows.value = result.items; total.value = result.total
  } catch { if (request === sequence) failed.value = true }
  finally { if (request === sequence) loading.value = false }
}
watch(identity, () => { selected.value.clear(); void load() }, { immediate: true, flush: 'sync' })
onScopeDispose(() => { sequence++ })
function toggle(row: Requirement, checked: boolean) {
  if (!checked) selected.value.delete(row.id)
  else if (!disabledReason(row) && selected.value.size < 50) selected.value.set(row.id, { ...row })
}
function allPage() { for (const row of rows.value) toggle(row, true) }
async function submit() {
  if (!selected.value.size || saving.value) return
  saving.value = true; error.value = ''; problems.value = []
  try {
    await api.post(`/versions/${props.versionId}/requirements/batch`, { version_revision: versionRevision, request_id: requestId, items: [...selected.value.values()].map(r => ({ requirement_id: r.id, revision: r.revision })) })
    emit('updated')
  } catch (e: any) {
    error.value = '本次未添加任何需求，请核对冲突项；版本已变更时，关闭并重新打开后再选择。'
    problems.value = e.response?.data?.data?.items || []
  } finally { saving.value = false }
}
</script>
<template>
  <div class="bulk-picker" v-loading="loading">
    <el-form inline @submit.prevent="page = 1; load()">
      <el-form-item label="关键词"><el-input v-model="filters.keyword" placeholder="编号 / 标题" maxlength="200" clearable /></el-form-item>
      <el-form-item label="阶段"><el-select v-model="filters.status" clearable><el-option v-for="s in REQUIREMENT_STATUSES" :key="s.value" :label="s.label" :value="s.value" /></el-select></el-form-item>
      <el-form-item label="优先级"><el-select v-model="filters.priority" clearable><el-option v-for="p in REQUIREMENT_PRIORITIES" :key="p.value" :label="p.label" :value="p.value" /></el-select></el-form-item>
      <el-button native-type="submit">搜索</el-button>
    </el-form>
    <p v-if="!props.systemId" role="alert">版本未指定业务系统，请先编辑版本补齐后再添加需求。</p>
    <p>已选 {{ selected.size }} / 50 条 · 跨页保留选择</p>
    <div class="bulk-tools"><el-button :disabled="saving" @click="allPage">选择当前页可用需求</el-button><el-button :disabled="saving" @click="selected.clear()">清空选择</el-button></div>
    <p v-if="failed">列表加载失败 <el-button link @click="load">重试</el-button></p>
    <ul v-else class="bulk-list"><li v-for="row in rows" :key="row.id"><el-checkbox :model-value="selected.has(row.id)" :disabled="saving || !!disabledReason(row) || (!selected.has(row.id) && selected.size >= 50)" @change="toggle(row, !!$event)"><span>{{ row.requirement_no }} · {{ row.title }}</span></el-checkbox><small>{{ requirementStatusLabel[row.status] }} · {{ row.priority }} {{ disabledReason(row) }}</small></li></ul>
    <el-pagination layout="prev, pager, next" :total="total" :page-size="20" :current-page="page" @current-change="page = $event; load()" />
    <details v-if="selected.size"><summary>查看已选需求</summary><p v-for="row in selected.values()" :key="row.id">{{ row.requirement_no }} · {{ row.title }} <el-button link :disabled="saving" @click="selected.delete(row.id)">移除选择</el-button></p></details>
    <div v-if="error" role="alert"><p>{{ error }}</p><p v-for="problem in problems" :key="problem.requirement_id">#{{ problem.requirement_id }}：{{ problem.reason }}</p></div>
    <div class="bulk-actions"><el-button :disabled="saving" @click="emit('cancel')">取消</el-button><el-button type="primary" :loading="saving" :disabled="!selected.size" @click="submit">添加 {{ selected.size }} 条需求</el-button></div>
  </div>
</template>
<style scoped>
.bulk-list { padding: 0; list-style: none; max-height: 360px; overflow: auto; }.bulk-list li { border-bottom: 1px solid var(--if-border, #eee); padding: 12px 0; }.bulk-list small { display: block; padding-left: 24px; color: var(--if-text-3); }.bulk-list :deep(.el-checkbox) { height: auto; max-width: 100%; }.bulk-list :deep(.el-checkbox__label) { white-space: normal; overflow-wrap: anywhere; }.bulk-picker :deep(.el-select) { width: 140px; }.bulk-tools,.bulk-actions { display: flex; flex-wrap: wrap; gap: 8px; }.bulk-actions { justify-content: flex-end; margin-top: 20px; }.bulk-picker :deep(.el-pagination) { max-width: 100%; }details { margin-top: 16px; }
</style>
