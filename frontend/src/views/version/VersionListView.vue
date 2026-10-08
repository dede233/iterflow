<script setup lang="ts">
import { onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { listVersions } from '@/api/versions'
import VersionCreateView from './VersionCreateView.vue'
import VersionDetailView from './VersionDetailView.vue'
import { useListQuery } from '@/composables/useListQuery'
import { useResponsive } from '@/composables/useResponsive'
import { usePermission } from '@/composables/usePermission'
import StatusTag from '@/components/StatusTag.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import ListCard from '@/components/ui/ListCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import ListFilterPanel from '@/components/ui/ListFilterPanel.vue'
import { VERSION_STATUSES, versionStatusLabel, versionStatusTagType } from '@/constants/version'
import type { VersionItem, VersionListParams } from '@/types/domain'

const router = useRouter()
const { isMobile } = useResponsive()
const { can } = usePermission()

const rows = ref<VersionItem[]>([])
const total = ref(0)
const loading = ref(false)
const failed = ref(false)
const createDialog = ref(false)
const filterDrawer = ref(false)
const detailDrawer = ref(false)
const activeVersionId = ref<number | null>(null)
const filters = reactive({ page: 1, page_size: 20, keyword: '', status: '' as VersionListParams['status'], owner_id: null as number | null })
const dateRange = ref<[string, string] | null>(null)
let requestSequence = 0
const positiveId = (value: number | null) => value != null && Number.isSafeInteger(value) && value >= 1 ? value : undefined

async function load(): Promise<void> {
  const q = queryState.applied()
  const current = { page: Number(q.page ?? 1), page_size: Number(q.page_size ?? 20), keyword: q.keyword ?? '', status: q.status as VersionListParams['status'], owner_id: q.owner_id ? Number(q.owner_id) : null }
  const currentRange = [q.planned_release_from, q.planned_release_to]

  const [from, to] = currentRange
  if (from && to && from > to) {
    ElMessage.warning('计划上线结束日期不能早于开始日期')
    return
  }
  const sequence = ++requestSequence
  loading.value = true
  failed.value = false
  try {
    const page = await listVersions({
      page: current.page, page_size: current.page_size,
      keyword: current.keyword.trim() || undefined, status: current.status || undefined,
      planned_release_from: from || undefined, planned_release_to: to || undefined,
      owner_id: positiveId(current.owner_id),
    })
    if (sequence !== requestSequence) return
    rows.value = page.items
    total.value = page.total
  } catch {
    if (sequence === requestSequence) failed.value = true
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function applyFilters(): void {
  if (dateRange.value && dateRange.value[0] > dateRange.value[1]) { ElMessage.warning('计划上线结束日期不能早于开始日期'); return }
  filterDrawer.value = false
  void queryState.apply()
}

function resetFilters(): void {
  filterDrawer.value = false
  void queryState.reset()
}

onBeforeUnmount(() => { requestSequence++ })

function openDetail(id: number): void {
  activeVersionId.value = id
  detailDrawer.value = true
}

function openFullScreen(id: number): void {
  detailDrawer.value = false
  void router.push(queryState.detail(`/versions/${id}`))
}

async function onVersionCreated(id: number): Promise<void> {
  createDialog.value = false
  await load()
  await router.push(queryState.detail(`/versions/${id}`))
}

const queryState = useListQuery({
  path: '/versions', readDraft: () => ({ ...filters, planned_release_from: dateRange.value?.[0], planned_release_to: dateRange.value?.[1] }),
  restore: q => {
    filters.page = Number(q.page ?? 1)
    filters.page_size = Number(q.page_size ?? 20)
    filters.keyword = (q.keyword ?? '') as typeof filters.keyword
    filters.status = (q.status ?? '') as typeof filters.status
    filters.owner_id = q.owner_id ? Number(q.owner_id) : null
    dateRange.value = q.planned_release_from && q.planned_release_to ? [q.planned_release_from, q.planned_release_to] : null
  },
  load, invalidate: () => { requestSequence++ },
})
</script>

<template>
  <section class="page">
    <PageHeader title="版本管理" description="规划版本范围、跟踪进度并准备发布。" eyebrow="研发协作">
      <template #actions>
      <el-button v-if="isMobile" @click="filterDrawer = true"><AppIcon name="filter" :size="16" />筛选</el-button>
      <el-button
        v-if="can('rd.version.create')"
        type="primary"
        @click="createDialog = true"
      >
        <AppIcon name="plus" :size="16" />新建版本
      </el-button>
      </template>
    </PageHeader>

    <ListFilterPanel v-model="filterDrawer" :mobile="isMobile" title="筛选版本" @search="applyFilters" @reset="resetFilters">
      <el-form-item label="关键词"><el-input v-model="filters.keyword" placeholder="版本号 / 名称" :maxlength="200" clearable @keyup.enter="applyFilters" /></el-form-item>
      <el-form-item label="状态"><el-select v-model="filters.status" clearable placeholder="全部"><el-option v-for="s in VERSION_STATUSES" :key="s.value" :label="s.label" :value="s.value" /></el-select></el-form-item>
      <el-form-item label="计划上线日期"><el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" popper-class="version-filter-date-popper" /></el-form-item>
      <el-form-item label="负责人 ID"><el-input-number v-model="filters.owner_id" :min="1" :precision="0" step-strictly controls-position="right" /></el-form-item>
    </ListFilterPanel>

    <ErrorState v-if="failed" title="版本加载失败" description="请检查网络后重试。" retry-label="重新加载" @retry="load" />
    <SectionCard v-else title="版本列表" :description="`共 ${total} 个版本`" :padded="false">
    <el-table
      v-if="!isMobile"
      v-loading="loading"
      :data="rows"
      row-key="id"
      @row-click="(row: VersionItem) => openDetail(row.id)"
    >
      <el-table-column prop="version_no" label="版本号" width="160" />
      <el-table-column prop="name" label="版本名称" min-width="200" show-overflow-tooltip />
      <el-table-column label="状态" width="110">
        <template #default="s">
          <StatusTag
            :status="s.row.status"
            :label="versionStatusLabel[s.row.status]"
            :type="versionStatusTagType(s.row.status)"
          />
        </template>
      </el-table-column>
      <el-table-column prop="planned_release_date" label="计划上线" width="140" />
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="s">
          <el-link type="primary" @click.stop="openDetail(s.row.id)">查看</el-link>
        </template>
      </el-table-column>
      <template #empty><EmptyState description="暂无版本" compact /></template>
    </el-table>

    <div v-else v-loading="loading" class="cards">
      <ListCard v-for="r in rows" :key="r.id" :code="r.version_no" :title="r.name" @open="openDetail(r.id)">
        <template #status>
          <StatusTag :status="r.status" :label="versionStatusLabel[r.status]" :type="versionStatusTagType(r.status)" size="sm" />
        </template>
        <span>计划上线：{{ r.planned_release_date || '-' }}</span>
      </ListCard>
      <EmptyState v-if="!loading && !rows.length" description="暂无版本" compact />
    </div>
    </SectionCard>

    <el-pagination
      class="pager"
      layout="prev, pager, next, total"
      :total="total"
      :current-page="filters.page"
      :page-size="filters.page_size"
      background
      @current-change="
        (p: number) => {
          void queryState.paginate(p)
        }
      "
    />

    <!-- Create Dialog -->
    <el-dialog v-model="createDialog" title="新建版本" class="create-dialog" width="min(720px, calc(100vw - 24px))" destroy-on-close :close-on-click-modal="false">
      <VersionCreateView v-if="createDialog" embedded @cancel="createDialog = false" @created="onVersionCreated" />
    </el-dialog>

    <!-- Scheme C: Detail Drawer with full-screen expansion support -->
    <el-drawer
      v-model="detailDrawer"
      title="版本详情"
      direction="rtl"
      size="min(960px, 94vw)"
      destroy-on-close
      class="detail-drawer"
    >
      <template #header>
        <div class="drawer-header-custom">
          <span class="drawer-title">版本详情</span>
          <el-button
            v-if="activeVersionId"
            size="small"
            class="expand-btn"
            @click="openFullScreen(activeVersionId)"
          >
            新标签/全屏直达
          </el-button>
        </div>
      </template>
      <VersionDetailView
        v-if="activeVersionId && detailDrawer"
        :key="activeVersionId"
        embedded
        :embedded-id="activeVersionId"
        @updated="load"
      />
    </el-drawer>
  </section>
</template>

<style scoped>
.cards { display: grid; gap: 8px; padding: var(--if-space-3); }
.pager { margin-top: var(--if-space-4); justify-content: flex-end; }
.drawer-header-custom { display: flex; align-items: center; justify-content: space-between; width: 100%; padding-right: 28px; }
.drawer-title { font-size: 16px; font-weight: 600; color: var(--if-text-primary); }
.expand-btn { margin-left: auto; }
@media (max-width: 767px) { .pager { justify-content: center; } }
</style>

<style>
@media (max-width: 767px) {
  .version-filter-date-popper .el-date-range-picker { width: min(340px, calc(100vw - 24px)); }
  .version-filter-date-popper .el-date-range-picker__content { width: 100%; float: none; }
  .version-filter-date-popper .el-date-range-picker__content.is-right { border-left: 0; border-top: 1px solid var(--if-border); }
  .version-filter-date-popper { max-height: calc(100vh - 24px); overflow-y: auto; }
}
</style>
