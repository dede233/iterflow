<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getAudit, listAudits } from '@/api/audits'
import { useResponsive } from '@/composables/useResponsive'
import type { AuditItem, AuditListParams } from '@/types/domain'

const { isMobile } = useResponsive()
const rows = ref<AuditItem[]>([])
const total = ref(0)
const loading = ref(false)
const detailLoading = ref(false)
const drawerVisible = ref(false)
const selected = ref<AuditItem | null>(null)
const timeRange = ref<[Date, Date] | null>(null)
const paging = reactive({ page: 1, size: 20 })
const filters = reactive({
  entity_type: '',
  entity_id: undefined as number | undefined,
  action: '',
  operator_id: undefined as number | undefined,
})

const entityTypes = ['FEEDBACK', 'REQUIREMENT', 'VERSION', 'RELEASE', 'USER', 'ROLE', 'AUTH']

function buildParams(): AuditListParams {
  return {
    page: paging.page,
    size: paging.size,
    entity_type: filters.entity_type || undefined,
    entity_id: filters.entity_id,
    action: filters.action.trim() || undefined,
    operator_id: filters.operator_id,
    time_from: timeRange.value?.[0]?.toISOString(),
    time_to: timeRange.value?.[1]?.toISOString(),
  }
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const result = await listAudits(buildParams())
    rows.value = result.items
    total.value = result.total
    paging.page = result.page
    paging.size = result.size
  } finally {
    loading.value = false
  }
}

function search(): void {
  paging.page = 1
  void load()
}

function reset(): void {
  Object.assign(filters, { entity_type: '', entity_id: undefined, action: '', operator_id: undefined })
  timeRange.value = null
  search()
}

async function showDetail(row: AuditItem): Promise<void> {
  detailLoading.value = true
  drawerVisible.value = true
  selected.value = null
  try {
    selected.value = await getAudit(row.id)
  } catch {
    drawerVisible.value = false
    ElMessage.error('审计记录不可访问或已不存在')
  } finally {
    detailLoading.value = false
  }
}

function formatTime(value: string): string {
  return new Date(value).toLocaleString()
}

function formatData(value: Record<string, unknown> | null | undefined): string {
  return value ? JSON.stringify(value, null, 2) : '无'
}

function operatorName(item: AuditItem): string {
  return item.operator ? `${item.operator.display_name}（${item.operator.username}）` : '系统'
}

onMounted(() => void load())
</script>

<template>
  <section class="page">
    <div class="head">
      <div>
        <h1 class="page-title">审计中心</h1>
        <p class="hint">仅展示当前账号有权查看且处于数据范围内的业务操作记录。</p>
      </div>
    </div>

    <el-form class="filters" label-position="top" @submit.prevent="search">
      <el-form-item label="实体类型">
        <el-select v-model="filters.entity_type" clearable placeholder="全部实体">
          <el-option v-for="item in entityTypes" :key="item" :label="item" :value="item" />
        </el-select>
      </el-form-item>
      <el-form-item label="实体 ID"><el-input-number v-model="filters.entity_id" :min="1" controls-position="right" /></el-form-item>
      <el-form-item label="操作"><el-input v-model="filters.action" clearable placeholder="如 STATUS_CHANGE" /></el-form-item>
      <el-form-item label="操作人 ID"><el-input-number v-model="filters.operator_id" :min="1" controls-position="right" /></el-form-item>
      <el-form-item label="时间范围" class="time-filter">
        <el-date-picker v-model="timeRange" type="datetimerange" range-separator="至" start-placeholder="开始时间" end-placeholder="结束时间" />
      </el-form-item>
      <div class="filter-actions">
        <el-button type="primary" native-type="submit">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>
    </el-form>

    <el-table v-if="!isMobile" v-loading="loading" :data="rows" class="audit-table" @row-click="showDetail">
      <el-table-column prop="id" label="ID" width="90" />
      <el-table-column prop="entity_type" label="实体" width="130" />
      <el-table-column prop="entity_id" label="实体 ID" width="110" />
      <el-table-column prop="action" label="操作" min-width="180" />
      <el-table-column label="操作人" min-width="160"><template #default="scope">{{ operatorName(scope.row) }}</template></el-table-column>
      <el-table-column label="时间" min-width="180"><template #default="scope">{{ formatTime(scope.row.created_at) }}</template></el-table-column>
      <el-table-column label="详情" width="80" fixed="right"><template #default="scope"><el-button link type="primary" @click.stop="showDetail(scope.row)">查看</el-button></template></el-table-column>
    </el-table>

    <div v-else v-loading="loading" class="cards">
      <el-card v-for="item in rows" :key="item.id" shadow="never" class="audit-card" @click="showDetail(item)">
        <div class="card-head"><strong>{{ item.entity_type }} #{{ item.entity_id ?? '-' }}</strong><el-tag size="small">{{ item.action }}</el-tag></div>
        <div class="card-meta">{{ operatorName(item) }} · {{ formatTime(item.created_at) }}</div>
      </el-card>
      <el-empty v-if="!loading && !rows.length" description="暂无可查看的审计记录" />
    </div>

    <el-pagination class="pager" layout="prev, pager, next, total" :total="total" :current-page="paging.page" :page-size="paging.size" background @current-change="(page: number) => { paging.page = page; void load() }" />

    <el-drawer v-model="drawerVisible" title="审计记录详情" size="min(620px, 100%)" destroy-on-close>
      <div v-loading="detailLoading" class="drawer-content">
        <template v-if="selected">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="记录 ID">{{ selected.id }}</el-descriptions-item>
            <el-descriptions-item label="实体">{{ selected.entity_type }} #{{ selected.entity_id ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="操作">{{ selected.action }}</el-descriptions-item>
            <el-descriptions-item label="操作人">{{ operatorName(selected) }}</el-descriptions-item>
            <el-descriptions-item label="发生时间">{{ formatTime(selected.created_at) }}</el-descriptions-item>
          </el-descriptions>
          <h3>变更前</h3><pre>{{ formatData(selected.before) }}</pre>
          <h3>变更后</h3><pre>{{ formatData(selected.after) }}</pre>
        </template>
      </div>
    </el-drawer>
  </section>
</template>

<style scoped>
.head { margin-bottom: 12px; }
.hint { margin: -8px 0 0; color: #64748b; font-size: 13px; }
.filters { display: grid; grid-template-columns: repeat(5, minmax(130px, 1fr)) auto; gap: 0 12px; align-items: end; padding: 14px; margin-bottom: 12px; border: 1px solid #e5e7eb; border-radius: 8px; }
.filters :deep(.el-form-item) { margin-bottom: 12px; }
.time-filter { min-width: 260px; }
.filter-actions { display: flex; gap: 8px; padding-bottom: 12px; }
.audit-table { cursor: pointer; }
.cards { display: grid; gap: 10px; }
.audit-card { cursor: pointer; }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.card-meta { margin-top: 10px; color: #64748b; font-size: 13px; }
.pager { margin-top: 16px; justify-content: flex-end; }
.drawer-content h3 { margin-top: 22px; font-size: 14px; }
pre { max-height: 280px; padding: 12px; overflow: auto; color: #334155; background: #f8fafc; border-radius: 6px; font-size: 12px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
@media (max-width: 1199px) { .filters { grid-template-columns: repeat(3, minmax(150px, 1fr)); } }
@media (max-width: 767px) { .filters { grid-template-columns: 1fr; } .time-filter { min-width: 0; } .filter-actions { padding-bottom: 0; } .pager { justify-content: center; } }
</style>
