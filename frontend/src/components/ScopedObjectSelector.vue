<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { listFeedbacks } from '@/api/feedbacks'
import { listRequirements } from '@/api/requirements'
import { listVersions } from '@/api/versions'
import { useScopedSearch, type SelectionOption } from '@/composables/useScopedSearch'
import { feedbackStatusLabel } from '@/constants/feedback'
import { requirementStatusLabel } from '@/constants/requirement'
import { versionStatusLabel } from '@/constants/version'
const props = defineProps<{ kind: 'feedback' | 'requirement' | 'version'; allowed: boolean; active: boolean; disabled?: boolean; excludeId?: number }>()
const model = defineModel<number | null>({ default: null })
const auth = useAuthStore()
const readable = computed(() => props.allowed && auth.hasPermission(`rd.${props.kind}.view`))
const names = { feedback: '反馈', requirement: '需求', version: '版本' }
const labels = { feedback: feedbackStatusLabel, requirement: requirementStatusLabel, version: versionStatusLabel }
const selected = ref<SelectionOption | null>(null)
const search = useScopedSearch(
  () => [readable.value && props.active && !props.disabled, `${auth.user?.id}:${auth.accessToken}:${auth.permissionCodes.join(',')}:${props.kind}`] as const,
  async (keyword, page) => {
    const params = { keyword: keyword || undefined, page, page_size: 20 }
    const result = props.kind === 'feedback' ? await listFeedbacks(params) : props.kind === 'requirement' ? await listRequirements(params) : await listVersions(params)
    return { total: result.total, items: result.items.filter(item => item.id !== props.excludeId).map(item => ({ id: item.id, code: 'version_no' in item ? item.version_no : 'requirement_no' in item ? item.requirement_no : item.feedback_no, title: 'name' in item ? item.name : item.title, status: item.status })) }
  },
)
watch(() => [props.active, model.value], () => { if (!props.active || model.value !== selected.value?.id) selected.value = null })
watch(() => [auth.user?.id, auth.accessToken, readable.value], () => { selected.value = null; model.value = null }, { flush: 'sync' })
function choose(option: SelectionOption) { model.value = option.id; selected.value = option; search.close() }
</script>
<template>
  <div class="object-selector">
    <template v-if="readable">
      <span class="selection-label">{{ selected ? `${selected.code} · ${selected.title}` : (model ? `#${model}` : '尚未选择') }}</span>
      <div class="selection-actions"><el-button :disabled="disabled || !active" @click="search.open">选择{{ names[kind] }}</el-button><el-button v-if="model" :disabled="disabled" @click="model = null; selected = null">清除</el-button></div>
    </template>
    <el-input-number v-else v-model="model" :disabled="disabled" :min="1" :precision="0" :aria-label="`${names[kind]} ID`" style="width: 100%" />
    <el-dialog :model-value="search.state.open" :title="`选择${names[kind]}`" width="min(640px, calc(100vw - 24px))" append-to-body destroy-on-close @update:model-value="(value: boolean) => { if (!value) search.close() }">
      <el-input :model-value="search.state.keyword" :aria-label="`搜索${names[kind]}`" placeholder="搜索编号或标题" :maxlength="200" clearable @update:model-value="search.search" />
      <div class="selector-results" :aria-busy="search.state.loading">
        <p v-if="search.state.loading" role="status">正在搜索…</p>
        <div v-else-if="search.state.error" role="alert">搜索失败，请重试。<el-button @click="search.retry">重试</el-button></div>
        <p v-else-if="!search.state.items.length">暂无可见结果</p>
        <button v-for="option in search.state.items" v-else :key="option.id" type="button" class="selector-option" @click="choose(option)"><strong>{{ option.code }}</strong><span>{{ option.title }}</span><small>{{ labels[kind][option.status] || option.status }}</small></button>
      </div>
      <el-pagination v-if="!search.state.loading && !search.state.error" layout="prev, pager, next" :current-page="search.state.page" :page-size="20" :total="search.state.total" @current-change="search.paginate" />
      <template #footer><el-button @click="search.close">取消</el-button></template>
    </el-dialog>
  </div>
</template>
<style scoped>
.object-selector { width: 100%; min-width: 0; }
.selection-label { display: block; overflow-wrap: anywhere; margin-bottom: 8px; }
.selection-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.selection-actions :deep(.el-button + .el-button) { margin-left: 0; }
.selector-results { min-height: 100px; margin: 12px 0; }
.selector-option { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 12px; width: 100%; margin-bottom: 8px; padding: 12px; border: 1px solid var(--if-border); border-radius: var(--if-radius); background: var(--if-bg-surface); color: var(--if-text-1); text-align: left; font: inherit; cursor: pointer; }
.selector-option span { overflow-wrap: anywhere; }
.selector-option:focus-visible, .selector-option:hover { outline: 2px solid var(--if-brand-500); }
@media (max-width: 767px) { .selector-option { grid-template-columns: minmax(0, 1fr) auto; } .selector-option span { grid-column: 1 / -1; grid-row: 2; } }
</style>
