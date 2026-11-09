<script setup lang="ts">
import { computed, onScopeDispose, reactive, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import { listBatches, versionTargets, createBatch, adjustBatch, cancelBatch, completeTarget, finalizeBatch, batchKindLabel, batchStatusLabel, platformLabel, type ReleaseBatch, type BatchTarget, type ReleaseTarget, type ReleaseBatches } from '@/api/targetReleases'
import type { VersionItem, PublishCheckItem } from '@/types/domain'
import { usePermission } from '@/composables/usePermission'
import { formatLocalDateTime } from '@/utils/dates'
import BusinessSystemSelect from '@/components/BusinessSystemSelect.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
const props = defineProps<{ version: VersionItem; readonly?: boolean }>()
const emit = defineEmits<{ updated: []; planState: [active: boolean] }>()
const { can } = usePermission()
const state = ref<ReleaseBatches | null>(null)
const loading = ref(false)
const failed = ref(false)
const page = ref(1)
const dialog = ref<'create' | 'adjust' | 'cancel' | 'complete' | 'finalize' | null>(null)
const selectedBatch = ref<ReleaseBatch | null>(null)
const selectedTarget = ref<BatchTarget | null>(null)
const targets = ref<ReleaseTarget[]>([])
const targetFailed = ref(false)
const targetLoading = ref(false)
const targetSearch = ref('')
const busy = ref(false)
const error = ref('')
const blockers = ref<PublishCheckItem[]>([])
const form = reactive({ kind: 'INITIAL' as ReleaseBatch['kind'], system_id: null as number | null, target_ids: [] as number[], release_notes: '', reason: '', released_at: '', notes: '', evidence: '' })
let sequence = 0
let optionsSequence = 0
const writable = computed(() => !props.readonly && can('rd.version.publish') && props.version.status !== 'CANCELED')
const active = (batch: ReleaseBatch) => ['PLANNED', 'IN_PROGRESS'].includes(batch.status)
const hasInitial = computed(() => props.version.release_frozen || state.value?.items.some(b => b.kind === 'INITIAL' && b.status !== 'CANCELED'))
const canCreate = computed(() => writable.value && !!state.value && (props.version.status === 'RELEASED' || (props.version.status === 'READY' && !hasInitial.value)))
const selectable = computed(() => targets.value.filter(t => {
  if (dialog.value === 'adjust') return selectedBatch.value?.targets.some(r => r.target_id === t.id && r.active) || (!t.pending && (form.kind === 'INITIAL' || (form.kind === 'REPUBLISH' ? t.covered : !t.covered)))
  return !t.pending && (form.kind === 'INITIAL' || (form.kind === 'REPUBLISH' ? t.covered : !t.covered))
}))
const lockedIds = computed(() => selectedBatch.value?.targets.filter(t => t.completed_at).map(t => t.target_id) ?? [])
const choices = computed(() => [
  ...selectable.value.map(t => ({ id: t.id, label: `${t.name} · ${platformLabel[t.platform]} · ${t.code}`, disabled: lockedIds.value.includes(t.id) })),
  ...(selectedBatch.value?.targets.filter(t => t.active && !selectable.value.some(o => o.id === t.target_id)).map(t => ({ id: t.target_id, label: `${t.name}（历史计划目标）`, disabled: !!t.completed_at })) ?? []),
])
async function load() {
  const seq = ++sequence; loading.value = true; failed.value = false
  try { const data = await listBatches(props.version.id, page.value); if (!Array.isArray(data.items)) throw new Error('Invalid batch response'); if (seq === sequence) { state.value = data; emit('planState', data.release_frozen || data.items.some(b => b.kind === 'INITIAL' && b.status !== 'CANCELED')) } }
  catch { if (seq === sequence) failed.value = true }
  finally { if (seq === sequence) loading.value = false }
}
watch(() => [props.version.id, props.version.revision], () => { dialog.value = null; void load() }, { immediate: true })
onScopeDispose(() => { sequence++; optionsSequence++ })
async function loadOptions() {
  const seq = ++optionsSequence; targetFailed.value = false; targetLoading.value = true
  try { const data = await versionTargets(props.version.id, form.system_id); if (seq === optionsSequence) targets.value = data }
  catch { if (seq === optionsSequence) targetFailed.value = true }
  finally { if (seq === optionsSequence) targetLoading.value = false }
}
function open(kind: NonNullable<typeof dialog.value>, batch: ReleaseBatch | null = null, target: BatchTarget | null = null) {
  selectedBatch.value = batch; selectedTarget.value = target; targetSearch.value = ''; error.value = ''; blockers.value = []; targets.value = []
  Object.assign(form, { kind: batch?.kind ?? (props.version.status === 'RELEASED' ? 'SUPPLEMENT' : 'INITIAL'), system_id: batch?.system_id ?? state.value?.system_id ?? props.version.system_id, target_ids: batch?.targets.filter(t => t.active).map(t => t.target_id) ?? [], release_notes: '', reason: '', released_at: new Date().toISOString(), notes: '', evidence: '' })
  dialog.value = kind
  if (kind === 'create' || kind === 'adjust') void loadOptions()
}
async function submit() {
  if (busy.value || !state.value || !dialog.value) return
  const mode = dialog.value; const batch = selectedBatch.value
  if (['create', 'adjust'].includes(mode) && (!form.target_ids.length || targetLoading.value || targetFailed.value)) { error.value = '请加载并选择至少一个发布目标'; return }
  if ((mode === 'create' && form.release_notes.trim().length < 2) || (['adjust', 'cancel'].includes(mode) && form.reason.trim().length < 2) || (mode === 'create' && form.kind === 'REPUBLISH' && form.reason.trim().length < 2)) { error.value = '请补充说明或原因（至少 2 个字符）'; return }
  if (mode === 'complete' && (!form.released_at || !Number.isFinite(Date.parse(form.released_at)))) { error.value = '请选择实际上线时间'; return }
  busy.value = true; error.value = ''; blockers.value = []
  try {
    const revision = state.value.version_revision
    if (mode === 'create') await createBatch(props.version.id, { version_revision: revision, kind: form.kind, system_id: form.system_id, target_ids: form.target_ids, release_notes: form.release_notes.trim(), reason: form.reason.trim() || null })
    if (mode === 'adjust' && batch) await adjustBatch(props.version.id, batch.id, { version_revision: revision, revision: batch.revision, target_ids: form.target_ids, reason: form.reason.trim() })
    if (mode === 'cancel' && batch) await cancelBatch(props.version.id, batch.id, { version_revision: revision, revision: batch.revision, reason: form.reason.trim() })
    if (mode === 'complete' && batch && selectedTarget.value) await completeTarget(props.version.id, batch.id, selectedTarget.value.id, { version_revision: revision, batch_revision: batch.revision, revision: selectedTarget.value.revision, released_at: new Date(form.released_at).toISOString(), notes: form.notes.trim() || null, evidence: form.evidence.trim() || null })
    if (mode === 'finalize' && batch) await finalizeBatch(props.version.id, batch, revision)
    dialog.value = null; ElMessage.success(mode === 'complete' ? '实际发布已登记' : '发布计划已更新'); await load(); emit('updated')
  } catch (e) {
    const data = isAxiosError(e) ? e.response?.data : null
    error.value = data?.message || '操作未完成，请检查网络并刷新核对后重试'
    blockers.value = data?.data?.checks ?? []
    if (data?.code === 40910) { dialog.value = null; await load(); emit('updated'); ElMessage.warning('发布信息已变更，请核对最新进度后重新操作') }
  } finally { busy.value = false }
}
</script>
<template>
  <SectionCard id="release-target-batches" title="发布目标与批次" :description="`累计覆盖 ${state?.coverage_count ?? 0} 个目标；首次计划全部完成后整体上线，后续补发保留原上线状态。`">
    <template #actions><el-button v-if="canCreate" type="primary" @click="open('create')">{{ version.status === 'RELEASED' ? '新增补发 / 重新发布' : '创建首次发布计划' }}</el-button></template>
    <ErrorState v-if="failed" title="发布批次加载失败" retry-label="重新加载" @retry="load" />
    <div v-else v-loading="loading">
      <el-alert v-if="state?.release_frozen && version.status !== 'RELEASED'" title="首次发布进行中，需求清单、内容及人员已冻结；剩余目标全部完成后整体上线。" type="warning" :closable="false" />
      <p v-if="state?.legacy_unrecorded" class="muted">历史发布，未记录目标。可从补发批次开始记录，不推断此前发布范围。</p>
      <p v-if="!state?.items.length && !loading" class="muted">暂无目标发布计划。发布检查通过后选择本次小程序，逐个登记外部实际发布结果。</p>
      <article v-for="batch in state?.items" :key="batch.id" class="batch">
        <div class="batch-head"><strong>{{ batchKindLabel[batch.kind] }} #{{ batch.id }}</strong><span>{{ batchStatusLabel[batch.status] }} · {{ batch.completed }}/{{ batch.total }}</span></div>
        <el-progress :percentage="batch.total ? Math.round(batch.completed / batch.total * 100) : 0" :status="batch.status === 'COMPLETED' ? 'success' : undefined" />
        <p class="notes">{{ batch.release_notes }}</p><p v-if="batch.reason" class="muted">原因：{{ batch.reason }}</p>
        <div v-if="writable && active(batch)" class="actions">
          <el-button size="small" @click="open('adjust', batch)">调整未完成目标</el-button>
          <el-button v-if="batch.kind !== 'INITIAL' || batch.completed === 0" size="small" @click="open('cancel', batch)">取消未完成部分</el-button>
          <el-button v-if="batch.kind === 'INITIAL' && batch.total > 0 && batch.completed === batch.total" size="small" type="primary" @click="open('finalize', batch)">确认整体上线</el-button>
        </div>
        <details :open="active(batch)"><summary>查看目标及实际记录</summary>
          <div v-for="target in batch.targets" :key="target.id" class="target-row">
            <div><strong>{{ target.name }}</strong><span class="muted">{{ platformLabel[target.platform] }} · {{ target.code }}<template v-if="target.app_id"> · {{ target.app_id }}</template></span></div>
            <template v-if="target.completed_at"><span class="success">已登记上线 · {{ formatLocalDateTime(target.completed_at) }}</span><small class="muted">登记人：{{ target.operator_name }} · 登记于 {{ formatLocalDateTime(target.recorded_at) }}</small><p v-if="target.notes" class="notes">{{ target.notes }}</p><p v-if="target.evidence" class="notes">凭证：{{ target.evidence }}</p></template>
            <span v-else-if="!target.active" class="muted">已移出计划：{{ target.removed_reason }}</span>
            <el-button v-else-if="writable && active(batch)" size="small" @click="open('complete', batch, target)">登记 {{ target.name }} 实际上线</el-button><span v-else class="muted">尚未登记实际上线</span>
          </div>
        </details>
      </article>
      <el-pagination v-if="state && state.total > 20" layout="prev, pager, next" :total="state.total" :current-page="page" :page-size="20" @current-change="(value: number) => { page = value; void load() }" />
    </div>
    <el-dialog :model-value="!!dialog" :title="dialog === 'create' ? '创建发布计划' : dialog === 'adjust' ? '调整目标计划' : dialog === 'cancel' ? '取消未完成目标' : dialog === 'finalize' ? '确认整体上线' : '登记目标实际上线'" width="min(600px, calc(100vw - 24px))" append-to-body :close-on-click-modal="!busy" :show-close="!busy" @close="dialog = null">
      <el-form label-position="top" @submit.prevent="submit">
        <template v-if="dialog === 'create' || dialog === 'adjust'">
          <el-form-item v-if="dialog === 'create' && version.status === 'RELEASED'" label="批次类型"><el-radio-group v-model="form.kind" @change="form.target_ids = []"><el-radio value="SUPPLEMENT">补发新目标</el-radio><el-radio value="REPUBLISH">已覆盖目标重新发布</el-radio></el-radio-group></el-form-item>
          <el-form-item v-if="!state?.system_id" label="本次所属业务系统" required><BusinessSystemSelect v-model="form.system_id" :clearable="false" @update:model-value="form.target_ids = []; loadOptions()" /></el-form-item>
          <p>仅选择本次计划覆盖的目标。首次发布开始后将冻结需求；已成功目标不能移除。</p>
          <el-form-item label="发布目标（可多选）" required>
            <el-input v-model="targetSearch" placeholder="搜索目标名称或编码" aria-label="搜索发布目标" clearable />
            <el-checkbox-group v-model="form.target_ids" class="target-choices" :max="50">
              <el-checkbox v-for="target in choices.filter(t => t.label.toLowerCase().includes(targetSearch.toLowerCase()))" :key="target.id" :value="target.id" :disabled="target.disabled">{{ target.label }}</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          <el-button v-if="targetFailed" link type="danger" @click="loadOptions">目标加载失败，重试</el-button>
          <p v-else-if="!targetLoading && !selectable.length" class="muted">暂无符合条件的启用目标，请联系管理员维护当前系统的发布目标，或检查其他未完成批次。</p>
          <el-form-item v-if="dialog === 'create'" label="本批发布说明" required><el-input v-model="form.release_notes" type="textarea" :rows="3" maxlength="5000" /></el-form-item>
        </template>
        <el-form-item v-if="dialog === 'adjust' || dialog === 'cancel' || (dialog === 'create' && form.kind === 'REPUBLISH')" label="原因" required><el-input v-model="form.reason" type="textarea" :rows="2" maxlength="500" /></el-form-item>
        <template v-if="dialog === 'complete'">
          <p>登记「{{ selectedTarget?.name }}」已经在外部实际上线的结果，不会自动操作小程序平台。成功记录不可撤销或改写。</p>
          <el-form-item label="实际上线时间" required><el-date-picker v-model="form.released_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ssZ" style="width:100%" /></el-form-item>
          <el-form-item label="说明（选填）"><el-input v-model="form.notes" type="textarea" maxlength="5000" /></el-form-item>
          <el-form-item label="凭证说明或链接（选填）"><el-input v-model="form.evidence" type="textarea" maxlength="1000" /></el-form-item>
        </template>
        <p v-if="dialog === 'cancel'">保留已成功记录，仅取消本批未完成目标。</p>
        <p v-if="dialog === 'finalize'">当前首次计划目标已全部登记成功。确认后生成整体发布记录，并将需求及反馈同步为已上线。</p>
        <el-alert v-if="error" :title="error" type="error" :closable="false" />
        <ul v-if="blockers.length"><li v-for="check in blockers.filter(c => !c.passed)" :key="check.type">{{ check.message }}</li></ul>
      </el-form>
      <template #footer><el-button :disabled="busy" @click="dialog = null">取消</el-button><el-button type="primary" :loading="busy" @click="submit">{{ dialog === 'complete' ? '确认实际已上线' : dialog === 'finalize' ? '确认整体上线' : '确认计划' }}</el-button></template>
    </el-dialog>
  </SectionCard>
</template>
<style scoped>
.target-choices { display:flex; flex-direction:column; width:100%; max-height:260px; overflow-y:auto; padding:8px 0; }
.target-choices :deep(.el-checkbox) { margin:0; height:auto; min-height:38px; white-space:normal; }
.target-choices :deep(.el-checkbox__label) { overflow-wrap:anywhere; }
.batch { margin-top:16px; padding:14px; border:1px solid var(--if-border); border-radius:var(--if-radius-sm); }
.batch-head,.actions { display:flex; flex-wrap:wrap; gap:8px; align-items:center; justify-content:space-between; }
.actions { justify-content:flex-start; margin-bottom:12px; }
.actions .el-button { margin-left:0; }
.muted { color:var(--if-text-3); font-size:13px; line-height:1.6; }
.notes { white-space:pre-wrap; overflow-wrap:anywhere; }
.target-row { display:grid; justify-items:start; gap:7px; padding:12px 0; border-top:1px solid var(--if-border); overflow-wrap:anywhere; }
.target-row strong,.target-row span { display:block; }
.success { color:var(--if-success-fg); }
summary { cursor:pointer; margin:12px 0; }
@media(max-width:600px) { .batch { padding:10px; } .actions .el-button { max-width:100%; height:auto; min-height:32px; white-space:normal; } }
</style>
