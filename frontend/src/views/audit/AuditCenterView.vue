<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getAudit, listAudits } from '@/api/audits'
import { useResponsive } from '@/composables/useResponsive'
import AppIcon from '@/components/ui/AppIcon.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import { formatLocalDateTime } from '@/utils/dates'
import type { AuditItem, AuditListParams } from '@/types/domain'

const { isMobile } = useResponsive()
const rows = ref<AuditItem[]>([])
const total = ref(0)
const loading = ref(false)
const failed = ref(false)
const filterDrawer = ref(false)
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
  failed.value = false
  try {
    const result = await listAudits(buildParams())
    rows.value = result.items
    total.value = result.total
    paging.page = result.page
    paging.size = result.size
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

function search(): void {
  paging.page = 1
  filterDrawer.value = false
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
    <PageHeader title="审计中心" description="查看当前账号权限与数据范围内的操作记录。" eyebrow="系统治理">
      <template v-if="isMobile" #actions>
        <el-button @click="filterDrawer = true"><AppIcon name="filter" :size="16" />筛选记录</el-button>
      </template>
    </PageHeader>

    <el-form v-if="!isMobile" class="filters filter-panel" label-position="top" @submit.prevent="search">
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

    <ErrorState v-if="failed" title="审计记录加载失败" description="请检查网络后重试。" retry-label="重新加载" @retry="load" />
    <SectionCard v-else title="操作记录" :description="`共 ${total} 条记录`" :padded="false">
    <el-table v-if="!isMobile" v-loading="loading" :data="rows" class="audit-table" @row-click="showDetail">
      <el-table-column prop="id" label="ID" width="90" />
      <el-table-column prop="entity_type" label="实体" width="130" />
      <el-table-column prop="entity_id" label="实体 ID" width="110" />
      <el-table-column prop="action" label="操作" min-width="180" />
      <el-table-column label="操作人" min-width="160"><template #default="scope">{{ operatorName(scope.row) }}</template></el-table-column>
      <el-table-column label="时间" min-width="180"><template #default="scope">{{ formatLocalDateTime(scope.row.created_at) }}</template></el-table-column>
      <el-table-column label="详情" width="80" fixed="right"><template #default="scope"><el-button link type="primary" @click.stop="showDetail(scope.row)">查看</el-button></template></el-table-column>
    </el-table>

    <div v-else v-loading="loading" class="cards">
      <button v-for="item in rows" :key="item.id" type="button" class="audit-card" @click="showDetail(item)">
        <span class="card-head"><strong>{{ item.entity_type }} #{{ item.entity_id ?? '-' }}</strong><span class="card-id">记录 #{{ item.id }}</span></span>
        <span class="card-action">{{ item.action }}</span>
        <span class="card-meta">{{ operatorName(item) }} · {{ formatLocalDateTime(item.created_at) }}</span>
      </button>
      <EmptyState v-if="!loading && !rows.length" description="暂无可查看的审计记录" compact />
    </div>
    </SectionCard>

    <el-pagination v-if="!failed" class="pager" layout="prev, pager, next, total" :total="total" :current-page="paging.page" :page-size="paging.size" background @current-change="(page: number) => { paging.page = page; void load() }" />

    <el-drawer v-model="filterDrawer" title="筛选审计记录" size="min(420px, 100%)" destroy-on-close>
      <el-form class="drawer-filters" label-position="top" @submit.prevent="search">
        <el-form-item label="实体类型"><el-select v-model="filters.entity_type" clearable placeholder="全部实体"><el-option v-for="item in entityTypes" :key="item" :label="item" :value="item" /></el-select></el-form-item>
        <el-form-item label="实体 ID"><el-input-number v-model="filters.entity_id" :min="1" controls-position="right" /></el-form-item>
        <el-form-item label="操作"><el-input v-model="filters.action" clearable placeholder="如 STATUS_CHANGE" /></el-form-item>
        <el-form-item label="操作人 ID"><el-input-number v-model="filters.operator_id" :min="1" controls-position="right" /></el-form-item>
        <el-form-item label="时间范围"><el-date-picker v-model="timeRange" type="datetimerange" range-separator="至" start-placeholder="开始时间" end-placeholder="结束时间" /></el-form-item>
      </el-form>
      <template #footer><div class="drawer-actions"><el-button @click="reset">重置</el-button><el-button type="primary" @click="search">查询</el-button></div></template>
    </el-drawer>

    <el-drawer v-model="drawerVisible" title="审计记录详情" size="min(620px, 100%)" destroy-on-close>
      <div v-loading="detailLoading" class="drawer-content">
        <template v-if="selected">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="记录 ID">{{ selected.id }}</el-descriptions-item>
            <el-descriptions-item label="实体">{{ selected.entity_type }} #{{ selected.entity_id ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="操作">{{ selected.action }}</el-descriptions-item>
            <el-descriptions-item label="操作人">{{ operatorName(selected) }}</el-descriptions-item>
            <el-descriptions-item label="发生时间">{{ formatLocalDateTime(selected.created_at) }}</el-descriptions-item>
          </el-descriptions>
          <h3>变更前</h3><pre>{{ formatData(selected.before) }}</pre>
          <h3>变更后</h3><pre>{{ formatData(selected.after) }}</pre>
        </template>
      </div>
    </el-drawer>
  </section>
</template>

<style scoped>
.filters { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0 12px; align-items: end; margin-bottom: var(--if-space-4); }
.filters :deep(.el-form-item) { margin-bottom: 12px; }
.filters :deep(.el-select), .filters :deep(.el-input-number), .filters :deep(.el-date-editor) { width: 100%; }
.time-filter { grid-column: span 3; }
.filter-actions { display: flex; gap: 8px; padding-bottom: 12px; }
.audit-table { cursor: pointer; }
.cards { display: grid; gap: 10px; padding: var(--if-space-4); }
.audit-card { display: grid; gap: 8px; width: 100%; min-width: 0; padding: 14px; background: var(--if-bg-surface); border: 1px solid var(--if-border); border-radius: var(--if-radius); color: var(--if-text-1); font: inherit; text-align: left; cursor: pointer; }
.audit-card:hover, .audit-card:focus-visible { border-color: var(--if-brand-500); box-shadow: var(--if-shadow); }
.card-head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; font-size: 13px; }
.card-id, .card-meta { color: var(--if-text-3); font-size: 12px; }
.card-action { color: var(--if-info-fg); font-family: var(--if-font-mono); font-size: 12px; overflow-wrap: anywhere; }
.pager { margin-top: var(--if-space-4); justify-content: flex-end; }
.drawer-filters :deep(.el-select), .drawer-filters :deep(.el-input-number), .drawer-filters :deep(.el-date-editor) { width: 100%; max-width: 100%; }
.drawer-actions { display: flex; justify-content: flex-end; gap: 8px; }
.drawer-content h3 { margin-top: 22px; font-size: 14px; }
pre { max-height: 280px; padding: 12px; overflow: auto; color: var(--if-text-2); background: var(--if-bg-subtle); border-radius: var(--if-radius-sm); font-size: 12px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
@media (max-width: 1199px) { .filters { grid-template-columns: repeat(2, minmax(0, 1fr)); } .time-filter { grid-column: span 2; } }
@media (max-width: 767px) { .pager { justify-content: center; } .drawer-filters :deep(.el-range-input) { min-width: 0; font-size: 11px; } }
</style>
