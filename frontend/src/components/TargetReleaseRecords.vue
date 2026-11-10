<script setup lang="ts">
import { onMounted, onScopeDispose, ref } from 'vue'
import { targetRecords, targetRecordOptions, batchKindLabel, platformLabel, type TargetRecord } from '@/api/targetReleases'
import { formatLocalDateTime } from '@/utils/dates'
import { usePermission } from '@/composables/usePermission'
import ReleaseVersionDrawer from '@/components/ReleaseVersionDrawer.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
const { can } = usePermission()
const rows = ref<TargetRecord[]>([])
const options = ref<{ id: number; label: string }[]>([])
const total = ref(0)
const page = ref(1)
const targetId = ref<number | null>(null)
const failed = ref(false)
const optionsFailed = ref(false)
const loading = ref(false)
const detail = ref(false)
const versionId = ref<number | null>(null)
let sequence = 0
async function load() {
  const seq = ++sequence; loading.value = true; failed.value = false
  try { const data = await targetRecords({ page: page.value, page_size: 20, target_id: targetId.value }); if (seq === sequence) { rows.value = data.items; total.value = data.total } }
  catch { if (seq === sequence) failed.value = true }
  finally { if (seq === sequence) loading.value = false }
}
async function loadOptions() {
  optionsFailed.value = false
  try { options.value = await targetRecordOptions() } catch { optionsFailed.value = true }
}
onMounted(() => { void load(); void loadOptions() })
onScopeDispose(() => { sequence++ })
</script>
<template>
  <section class="records">
    <p>记录版本已发布到哪些小程序或 PC；补记目标不会改变版本上线时间。</p>
    <el-select v-model="targetId" filterable clearable placeholder="按发布目标筛选" aria-label="发布目标筛选" style="width:min(100%, 400px)" @change="page = 1; load()"><el-option v-for="target in options" :key="target.id" :label="target.label" :value="target.id" /></el-select>
    <el-button v-if="optionsFailed" link @click="loadOptions">筛选目标加载失败，重试</el-button>
    <ErrorState v-if="failed" title="目标发布记录加载失败" retry-label="重新加载" @retry="load" />
    <div v-else v-loading="loading">
      <article v-for="record in rows" :key="record.id" class="record">
        <strong>{{ record.name }} · {{ record.version_no }}</strong>
        <p>{{ platformLabel[record.platform] }} · {{ record.version_name }} · {{ batchKindLabel[record.batch_kind] }} #{{ record.batch_id }}</p>
        <p>实际上线：{{ formatLocalDateTime(record.completed_at) }} · 登记人：{{ record.operator_name }}</p>
        <small>登记于 {{ formatLocalDateTime(record.recorded_at) }} · 目标编码 {{ record.code }}<template v-if="record.app_id"> · AppID {{ record.app_id }}</template></small>
        <p v-if="record.notes">{{ record.notes }}</p><p v-if="record.evidence">凭证：{{ record.evidence }}</p>
        <el-button v-if="can('rd.version.view')" link type="primary" @click="versionId = record.version_id; detail = true">查看版本与全部目标</el-button>
      </article>
      <p v-if="!loading && !rows.length">暂无目标实际发布记录，历史整体发布不会推断目标。</p>
    </div>
    <el-pagination v-if="total > 0" layout="prev, pager, next, total" :total="total" :page-size="20" :current-page="page" @current-change="(value: number) => { page = value; void load() }" />
    <ReleaseVersionDrawer v-model="detail" kind="version" :id="versionId" return-to="/releases" />
  </section>
</template>
<style scoped>
.records { padding:16px; }
.record { margin-top:12px; border:1px solid var(--if-border); border-radius:var(--if-radius-sm); padding:14px; overflow-wrap:anywhere; }
.record p { white-space:pre-wrap; line-height:1.6; margin:8px 0; }
.record small,.records > p { color:var(--if-text-2); }
</style>
