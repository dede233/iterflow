<script setup lang="ts">
import { computed, onScopeDispose, reactive, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import { listBatches, recordCoverage, platformLabel, type ReleaseBatches } from '@/api/targetReleases'
import type { VersionItem } from '@/types/domain'
import { usePermission } from '@/composables/usePermission'
import { formatLocalDateTime } from '@/utils/dates'
import BusinessSystemSelect from '@/components/BusinessSystemSelect.vue'
import PublishedTargetSelect from '@/components/PublishedTargetSelect.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
const props = defineProps<{ version: VersionItem; readonly?: boolean }>()
const emit = defineEmits<{ updated: [] }>()
const { can } = usePermission()
const state = ref<ReleaseBatches | null>(null)
const loading = ref(false), failed = ref(false), dialog = ref(false), busy = ref(false), ready = ref(false)
const page = ref(1), error = ref('')
const form = reactive({ system_id: null as number | null, target_ids: [] as number[], released_at: '', notes: '', evidence: '' })
let sequence = 0
const writable = computed(() => !props.readonly && can('rd.version.publish') && props.version.status === 'RELEASED')
async function load() {
  const seq = ++sequence; loading.value = true; failed.value = false
  try { const data = await listBatches(props.version.id, page.value); if (!Array.isArray(data.items)) throw new Error('Invalid coverage response'); if (seq === sequence) state.value = data }
  catch { if (seq === sequence) failed.value = true }
  finally { if (seq === sequence) loading.value = false }
}
watch(() => [props.version.id, props.version.revision], () => { page.value = 1; state.value = null; dialog.value = false; void load() }, { immediate: true })
onScopeDispose(() => { sequence++ })
function open() {
  error.value = ''; ready.value = false
  Object.assign(form, { system_id: state.value?.system_id ?? props.version.system_id, target_ids: [], released_at: new Date().toISOString(), notes: '', evidence: '' })
  dialog.value = true
}
async function submit() {
  if (busy.value || !state.value || !writable.value) return
  if (!ready.value || !form.target_ids.length) { error.value = '请勾选至少一个已经发布的目标'; return }
  if (!form.released_at || !Number.isFinite(Date.parse(form.released_at))) { error.value = '请选择实际上线时间'; return }
  const id = props.version.id
  busy.value = true; error.value = ''
  try {
    await recordCoverage(id, { version_revision: state.value.version_revision, system_id: form.system_id, target_ids: [...form.target_ids], released_at: new Date(form.released_at).toISOString(), notes: form.notes.trim() || null, evidence: form.evidence.trim() || null })
    if (id !== props.version.id) return
    dialog.value = false; ElMessage.success('已发布目标已记录'); await load(); emit('updated')
  } catch (e) {
    if (id !== props.version.id) return
    const data = isAxiosError(e) ? e.response?.data : null
    error.value = data?.message || '结果尚未确认，请刷新核对发布记录后再操作'
    if (data?.code === 40910) { dialog.value = false; await load(); emit('updated'); ElMessage.warning('发布信息已变更，请核对最新记录后重新操作') }
  } finally { busy.value = false }
}
</script>
<template>
  <SectionCard id="release-target-batches" title="已发布目标" :description="`已记录 ${state?.coverage_count ?? 0} 个小程序 / PC 目标；仅管理发布覆盖范围，不影响版本上线状态。`">
    <template #actions><el-button v-if="writable && state && !failed" type="primary" @click="open">补记已发布目标</el-button></template>
    <ErrorState v-if="failed" title="发布目标记录加载失败" retry-label="重新加载" @retry="load" />
    <div v-else v-loading="loading">
      <p v-if="!state?.coverage_count && !loading" class="muted">尚未记录发布目标。可在发布版本时勾选，或发布后补记，不推断历史发布范围。</p>
      <p v-if="version.status !== 'RELEASED'" class="muted">通过版本发布检查后正常发布，无需先创建目标计划。</p>
      <details v-for="batch in state?.items" :key="batch.id" class="batch">
        <summary>{{ formatLocalDateTime(batch.created_at) }} · {{ batch.targets.filter(t => t.completed_at).length }} 个已发布目标 · {{ batch.targets.filter(t => t.completed_at).map(t => t.name).join('、') }}<span v-if="batch.status !== 'COMPLETED'">（旧计划历史）</span></summary>
        <div v-for="target in batch.targets" :key="target.id" class="target-row">
          <strong>{{ target.name }} · {{ platformLabel[target.platform] }}</strong>
          <template v-if="target.completed_at"><span class="success">已发布 · {{ formatLocalDateTime(target.completed_at) }}</span><small class="muted">登记人：{{ target.operator_name }} · 登记于 {{ formatLocalDateTime(target.recorded_at) }}</small><p v-if="target.notes" class="notes">{{ target.notes }}</p><p v-if="target.evidence" class="notes">凭证：{{ target.evidence }}</p></template>
          <span v-else class="muted">旧计划未登记发布，不计入已发布范围</span>
        </div>
      </details>
      <el-pagination v-if="state && state.total > 20" layout="prev, pager, next" :total="state.total" :current-page="page" :page-size="20" @current-change="(value: number) => { page = value; void load() }" />
    </div>
    <el-dialog v-model="dialog" title="补记已发布目标" width="min(600px, calc(100vw - 24px))" append-to-body destroy-on-close :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
      <p>勾选此版本已经发布的小程序或 PC。保存只补充记录，原版本上线时间与需求状态保持不变。</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item v-if="dialog && state && !state.system_id" label="目标所属业务系统" required><BusinessSystemSelect v-model="form.system_id" :clearable="false" :disabled="busy" /></el-form-item>
        <el-form-item label="已发布目标（可多选）" required><PublishedTargetSelect v-model="form.target_ids" :version-id="version.id" :system-id="form.system_id" :active="dialog" :disabled="busy" @ready="ready = $event" /></el-form-item>
        <el-form-item label="实际上线时间" required><el-date-picker v-model="form.released_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ssZ" style="width:100%" :disabled="busy" /></el-form-item>
        <el-form-item label="说明（选填）"><el-input v-model="form.notes" type="textarea" maxlength="5000" :disabled="busy" /></el-form-item>
        <el-form-item label="凭证说明或链接（选填）"><el-input v-model="form.evidence" type="textarea" maxlength="1000" :disabled="busy" /></el-form-item>
        <el-alert v-if="error" :title="error" type="error" :closable="false" />
      </el-form>
      <template #footer><el-button :disabled="busy" @click="dialog = false">取消</el-button><el-button type="primary" :loading="busy" :disabled="!ready" @click="submit">保存已发布目标</el-button></template>
    </el-dialog>
  </SectionCard>
</template>
<style scoped>
.batch { margin-top:12px; padding:12px; border:1px solid var(--if-border); border-radius:var(--if-radius-sm); }
.muted { color:var(--if-text-3); font-size:13px; line-height:1.6; }
.notes { margin:0; white-space:pre-wrap; overflow-wrap:anywhere; }
.target-row { display:grid; justify-items:start; gap:7px; padding:12px 0; border-top:1px solid var(--if-border); overflow-wrap:anywhere; }
.success { color:var(--if-success-fg); }
summary { cursor:pointer; overflow-wrap:anywhere; line-height:1.7; }
</style>
