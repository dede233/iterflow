<script setup lang="ts">
import { computed, onScopeDispose, reactive, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import { listBatches, recordCoverage, platformLabel, type ReleaseBatches } from '@/api/targetReleases'
import { groupReleaseCoverage, type CoverageGroup } from '@/utils/releaseCoverage'
import type { MiniProgramPlatform } from '@/utils/releaseTargetGroups'
import type { VersionItem } from '@/types/domain'
import { usePermission } from '@/composables/usePermission'
import { formatLocalDateTime } from '@/utils/dates'
import BusinessSystemSelect from '@/components/BusinessSystemSelect.vue'
import PublishedTargetSelect from '@/components/PublishedTargetSelect.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
const props = defineProps<{ version: VersionItem; readonly?: boolean }>()
const emit = defineEmits<{ updated: [] }>()
const { can } = usePermission()
const state = ref<ReleaseBatches | null>(null)
const loading = ref(false), failed = ref(false), dialog = ref(false), busy = ref(false), ready = ref(false)
const page = ref(1), error = ref('')
const loadingAll = ref(false), moreError = ref('')
const form = reactive({ system_id: null as number | null, target_ids: [] as number[], released_at: '', notes: '', evidence: '' })
const savedForm = ref('')
const { requestLeave } = useUnsavedChanges({
  isDirty: () => JSON.stringify(form) !== savedForm.value,
  isBusy: () => busy.value,
  active: () => dialog.value,
})
async function requestClose(): Promise<boolean> {
  if (busy.value || !await requestLeave()) return false
  dialog.value = false
  return true
}
async function beforeClose(done: () => void): Promise<void> { if (await requestClose()) done() }
defineExpose({ requestClose })
let sequence = 0
let moreSequence = 0
const coverageGroups = computed(() => groupReleaseCoverage(state.value?.items ?? []))
const coverageComplete = computed(() => !!state.value && state.value.items.length >= state.value.total)
const miniPlatforms: MiniProgramPlatform[] = ['WECHAT_MINI_PROGRAM', 'ALIPAY_MINI_PROGRAM']
const coverageMember = (group: CoverageGroup, platform: MiniProgramPlatform) => group.members.find(m => m.target.platform === platform)
const writable = computed(() => !props.readonly && can('rd.version.publish') && props.version.status === 'RELEASED')
async function load() {
  stopLoadingAll(); moreError.value = ''; page.value = 1
  const seq = ++sequence; loading.value = true; failed.value = false
  try { const data = await listBatches(props.version.id, page.value); if (!Array.isArray(data.items)) throw new Error('Invalid coverage response'); if (seq === sequence) state.value = data }
  catch { if (seq === sequence) failed.value = true }
  finally { if (seq === sequence) loading.value = false }
}
function stopLoadingAll() { moreSequence++; loadingAll.value = false }
async function loadCompleteCoverage() {
  if (!state.value || loading.value || loadingAll.value || coverageComplete.value) return
  const id = props.version.id, seq = ++moreSequence
  loadingAll.value = true; moreError.value = ''
  try {
    // Bound each user-triggered pass. A large history can be continued explicitly.
    for (let count = 0; count < 50 && state.value && !coverageComplete.value; count++) {
      const before: ReleaseBatches = state.value
      const nextPage = page.value + 1
      const data = await listBatches(id, nextPage)
      if (seq !== moreSequence || id !== props.version.id) return
      if (data.version_id !== id || data.version_revision !== before.version_revision || data.total !== before.total ||
          data.page !== nextPage || data.page_size !== before.page_size || !Array.isArray(data.items) || !data.items.length ||
          data.items.some(batch => before.items.some(old => old.id === batch.id))) {
        moreError.value = '发布记录已变化，请重新加载后查看完整覆盖。'; return
      }
      state.value = { ...data, items: [...before.items, ...data.items] }
      page.value = nextPage
    }
  } catch { if (seq === moreSequence) moreError.value = '其余记录加载失败，已加载的记录仍可查看。' }
  finally { if (seq === moreSequence) loadingAll.value = false }
}
watch(() => [props.version.id, props.version.revision], () => { page.value = 1; state.value = null; dialog.value = false; void load() }, { immediate: true })
onScopeDispose(() => { sequence++; stopLoadingAll() })
function open() {
  if (!writable.value || busy.value || loading.value || failed.value) return
  error.value = ''; ready.value = false
  Object.assign(form, { system_id: state.value?.system_id ?? props.version.system_id, target_ids: [], released_at: new Date().toISOString(), notes: '', evidence: '' })
  savedForm.value = JSON.stringify(form)
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
  <SectionCard id="release-target-batches" title="已发布目标" :description="state && !failed ? `已记录 ${state.coverage_count} 个平台 / PC 站点` : undefined">
    <template #actions><el-button v-if="writable && state && !failed" type="primary" @click="open">补记已发布目标</el-button></template>
    <ErrorState v-if="failed" title="发布目标记录加载失败" retry-label="重新加载" @retry="load" />
    <div v-else v-loading="loading">
      <p v-if="!state?.coverage_count && !loading" class="muted">尚未记录发布目标。可在发布版本时勾选，或发布后补记，不推断历史发布范围。</p>
      <p v-if="state && state.total" class="coverage-scope" role="status">
        {{ coverageComplete ? '完整发布覆盖' : '已加载记录的覆盖范围' }} · 已加载 {{ state.items.length }} / {{ state.total }} 批登记
        <span v-if="!coverageComplete">，其余记录可能包含其他平台或更新的上线时间。</span>
      </p>
      <div v-if="coverageGroups.length" class="coverage-matrix" aria-label="按品牌查看发布覆盖">
        <div class="coverage-heading" aria-hidden="true"><span>品牌 / 站点</span><template v-if="coverageGroups.some(group => group.kind === 'MINI_PROGRAM')"><span>微信小程序</span><span>支付宝小程序</span></template><span v-else class="pc-coverage">PC Web 实际上线时间</span></div>
        <article v-for="group in coverageGroups" :key="group.key" class="coverage-brand" :aria-label="`${group.name}发布覆盖`">
          <header><strong>{{ group.name }}</strong><small>{{ group.code }}</small></header>
          <template v-if="group.kind === 'MINI_PROGRAM'">
            <div v-for="platform in miniPlatforms" :key="platform" class="coverage-platform" :aria-label="platformLabel[platform]">
              <span class="mobile-platform">{{ platformLabel[platform] }}</span>
              <template v-if="coverageMember(group, platform)">
                <span class="success">已记录发布</span>
                <time :datetime="coverageMember(group, platform)!.target.completed_at!">{{ formatLocalDateTime(coverageMember(group, platform)!.target.completed_at) }}</time>
                <small v-if="coverageMember(group, platform)!.recordCount > 1">最近实际上线 · {{ coverageMember(group, platform)!.recordCount }} 次记录</small>
              </template>
              <span v-else class="muted">{{ coverageComplete ? '未记录发布' : '当前范围未记录' }}</span>
            </div>
          </template>
          <div v-else class="coverage-platform pc-coverage"><span class="success">PC Web · 已记录发布</span><time :datetime="group.members[0].target.completed_at!">{{ formatLocalDateTime(group.members[0].target.completed_at) }}</time><small v-if="group.members[0].recordCount > 1">最近实际上线 · {{ group.members[0].recordCount }} 次记录</small></div>
        </article>
      </div>
      <p v-else-if="state?.coverage_count && !loading" class="muted">当前范围尚无实际发布记录，请加载其余记录查看覆盖情况。</p>
      <div v-if="state && !coverageComplete" class="coverage-load">
        <el-button v-if="!loadingAll" :disabled="loading" @click="loadCompleteCoverage">加载完整覆盖</el-button>
        <el-button v-else @click="stopLoadingAll">停止加载</el-button>
        <span v-if="loadingAll" role="status">正在读取其余登记记录…</span>
      </div>
      <p v-if="moreError" class="load-error" role="alert">{{ moreError }} <el-button link @click="load">重新加载</el-button></p>
      <details v-if="state?.items.length" class="coverage-history">
        <summary>登记历史与说明 · {{ state.items.length }} 批{{ coverageComplete ? '' : '（已加载）' }}</summary>
        <details v-for="batch in state.items" :key="batch.id" class="batch">
          <summary>{{ formatLocalDateTime(batch.created_at) }} · {{ batch.targets.filter(t => t.completed_at).length }} 个已发布目标<span v-if="batch.kind === 'REPUBLISH'"> · 重新发布</span><span v-if="batch.status !== 'COMPLETED'">（旧计划历史）</span></summary>
          <div v-for="target in batch.targets" :key="target.id" class="target-row">
            <strong>{{ target.name }} · {{ platformLabel[target.platform] }}</strong>
            <template v-if="target.completed_at"><span class="success">已发布 · {{ formatLocalDateTime(target.completed_at) }}</span><small class="muted">登记人：{{ target.operator_name }} · 登记于 {{ formatLocalDateTime(target.recorded_at) }}</small><p v-if="target.notes" class="notes">{{ target.notes }}</p><p v-if="target.evidence" class="notes">凭证：{{ target.evidence }}</p></template>
            <span v-else class="muted">旧计划未登记发布，不计入已发布范围</span>
          </div>
        </details>
      </details>
      <details class="coverage-help"><summary>发布记录说明</summary><p class="muted">仅管理发布覆盖范围，不影响版本上线状态。未记录不代表尚未发布；历史记录保留登记时的名称与平台信息。</p><p v-if="version.status !== 'RELEASED'" class="muted">通过版本发布检查后正常发布，无需先创建目标计划。</p></details>
    </div>
    <el-dialog v-model="dialog" title="补记已发布目标" width="min(600px, calc(100vw - 24px))" append-to-body destroy-on-close :before-close="beforeClose" :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
      <p>勾选此版本已经发布的小程序或 PC。保存只补充记录，原版本上线时间与需求状态保持不变。</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item v-if="dialog && state && !state.system_id" label="目标所属业务系统" required><BusinessSystemSelect v-model="form.system_id" :clearable="false" :disabled="busy" /></el-form-item>
        <el-form-item label="已发布目标（可多选）" required><PublishedTargetSelect v-model="form.target_ids" :version-id="version.id" :system-id="form.system_id" :active="dialog" :disabled="busy" @ready="ready = $event" /></el-form-item>
        <el-form-item label="实际上线时间" required><el-date-picker v-model="form.released_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ssZ" style="width:100%" :disabled="busy" /></el-form-item>
        <el-form-item label="说明（选填）"><el-input v-model="form.notes" type="textarea" maxlength="5000" :disabled="busy" /></el-form-item>
        <el-form-item label="凭证说明或链接（选填）"><el-input v-model="form.evidence" type="textarea" maxlength="1000" :disabled="busy" /></el-form-item>
        <el-alert v-if="error" :title="error" type="error" :closable="false" />
      </el-form>
      <template #footer><el-button :disabled="busy" @click="requestClose">取消</el-button><el-button type="primary" :loading="busy" :disabled="!ready" @click="submit">保存已发布目标</el-button></template>
    </el-dialog>
  </SectionCard>
</template>
<style scoped>
.coverage-scope { color:var(--if-text-2); font-size:13px; line-height:1.6; margin:0 0 12px; }
.coverage-matrix { border:1px solid var(--if-border); border-radius:var(--if-radius); overflow:hidden; }
.coverage-heading,.coverage-brand { display:grid; grid-template-columns:minmax(140px,1fr) repeat(2,minmax(150px,1fr)); gap:16px; padding:14px 16px; }
.coverage-heading { background:var(--if-bg-page); font-size:13px; color:var(--if-text-2); }
.coverage-brand { border-top:1px solid var(--if-border); font-size:14px; }
.coverage-brand header,.coverage-platform { min-width:0; overflow-wrap:anywhere; }
.coverage-brand small { display:block; color:var(--if-text-3); font-size:12px; line-height:1.6; margin-top:5px; }
.coverage-platform time { display:block; font-size:13px; line-height:1.6; margin-top:5px; font-variant-numeric:tabular-nums; }
.pc-coverage { grid-column:span 2; }
.mobile-platform { display:none; }
.coverage-load { display:flex; align-items:center; flex-wrap:wrap; gap:12px; margin-top:12px; font-size:13px; color:var(--if-text-2); }
.coverage-history,.coverage-help { margin-top:16px; color:var(--if-text-2); font-size:13px; }
.load-error { color:var(--if-danger-fg); font-size:13px; }
.batch { margin-top:12px; padding:12px; border:1px solid var(--if-border); border-radius:var(--if-radius-sm); }
.muted { color:var(--if-text-3); font-size:13px; line-height:1.6; }
.notes { margin:0; white-space:pre-wrap; overflow-wrap:anywhere; }
.target-row { display:grid; justify-items:start; gap:7px; padding:12px 0; border-top:1px solid var(--if-border); overflow-wrap:anywhere; }
.success { color:var(--if-success-fg); }
summary { cursor:pointer; overflow-wrap:anywhere; line-height:1.7; }
@media(max-width:767px) {
  .coverage-heading { display:none; }
  .coverage-brand { grid-template-columns:1fr; gap:12px; }
  .coverage-brand:first-of-type { border-top:0; }
  .coverage-platform { border-top:1px solid var(--if-border); padding-top:12px; }
  .pc-coverage { grid-column:auto; }
  .mobile-platform { display:inline; margin-right:12px; }
  .coverage-history > summary,.coverage-help > summary,.batch > summary { min-height:44px; padding:10px 0; box-sizing:border-box; }
  .coverage-load :deep(.el-button) { min-height:44px; }
}
</style>
