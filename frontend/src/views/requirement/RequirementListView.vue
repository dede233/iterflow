<script setup lang="ts">
import { onBeforeUnmount, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listRequirements } from '@/api/requirements'
import RequirementCreateView from './RequirementCreateView.vue'
import RequirementDetailView from './RequirementDetailView.vue'
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
import { REQUIREMENT_PRIORITIES, REQUIREMENT_STATUSES, requirementStatusLabel, requirementStatusTagType } from '@/constants/requirement'
import type { Requirement, RequirementListParams } from '@/types/domain'

const router = useRouter()
const { isMobile } = useResponsive()
const { can } = usePermission()

const rows = ref<Requirement[]>([])
const total = ref(0)
const loading = ref(false)
const failed = ref(false)
const createDialog = ref(false)
const filterDrawer = ref(false)
const detailDrawer = ref(false)
const activeRequirementId = ref<number | null>(null)
const filters = reactive({ page: 1, page_size: 20, keyword: '', status: '' as RequirementListParams['status'], priority: '' as RequirementListParams['priority'], source: '' as RequirementListParams['source'], current_version_id: null as number | null, owner_id: null as number | null })
let requestSequence = 0
const positiveId = (value: number | null) => value != null && Number.isSafeInteger(value) && value >= 1 ? value : undefined

async function load(): Promise<void> {
  const q = queryState.applied()
  const current = { page: Number(q.page ?? 1), page_size: Number(q.page_size ?? 20), keyword: q.keyword ?? '', status: q.status as RequirementListParams['status'], priority: q.priority as RequirementListParams['priority'], source: q.source as RequirementListParams['source'], current_version_id: q.current_version_id ? Number(q.current_version_id) : null, owner_id: q.owner_id ? Number(q.owner_id) : null }

  const sequence = ++requestSequence
  loading.value = true
  failed.value = false
  try {
    const page = await listRequirements({
      page: current.page, page_size: current.page_size,
      keyword: current.keyword.trim() || undefined, status: current.status || undefined,
      priority: current.priority || undefined, source: current.source || undefined,
      current_version_id: positiveId(current.current_version_id), owner_id: positiveId(current.owner_id),
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
  filterDrawer.value = false
  void queryState.apply()
}

function resetFilters(): void {
  filterDrawer.value = false
  void queryState.reset()
}

onBeforeUnmount(() => { requestSequence++ })

function openDetail(id: number): void {
  activeRequirementId.value = id
  detailDrawer.value = true
}

function openFullScreen(id: number): void {
  detailDrawer.value = false
  void router.push(queryState.detail(`/requirements/${id}`))
}

async function onRequirementCreated(id: number): Promise<void> {
  createDialog.value = false
  await load()
  await router.push(queryState.detail(`/requirements/${id}`))
}

const queryState = useListQuery({
  path: '/requirements', readDraft: () => ({ ...filters }),
  restore: q => {
    filters.page = Number(q.page ?? 1)
    filters.page_size = Number(q.page_size ?? 20)
    filters.keyword = (q.keyword ?? '') as typeof filters.keyword
    filters.status = (q.status ?? '') as typeof filters.status
    filters.priority = (q.priority ?? '') as typeof filters.priority
    filters.source = (q.source ?? '') as typeof filters.source
    filters.current_version_id = q.current_version_id ? Number(q.current_version_id) : null
    filters.owner_id = q.owner_id ? Number(q.owner_id) : null
  },
  load, invalidate: () => { requestSequence++ },
})
</script>

<template>
  <section class="page">
    <PageHeader title="需求管理" description="从确认、排期到交付，清晰跟进每项研发需求。" eyebrow="研发协作">
      <template #actions>
      <el-button v-if="isMobile" @click="filterDrawer = true"><AppIcon name="filter" :size="16" />筛选</el-button>
      <el-button
        v-if="can('rd.requirement.create')"
        type="primary"
        @click="createDialog = true"
      >
        <AppIcon name="plus" :size="16" />新建需求
      </el-button>
      </template>
    </PageHeader>

    <ListFilterPanel v-model="filterDrawer" :mobile="isMobile" title="筛选需求" @search="applyFilters" @reset="resetFilters">
      <el-form-item label="关键词"><el-input v-model="filters.keyword" placeholder="编号 / 标题" :maxlength="200" clearable @keyup.enter="applyFilters" /></el-form-item>
      <el-form-item label="状态"><el-select v-model="filters.status" clearable placeholder="全部"><el-option v-for="s in REQUIREMENT_STATUSES" :key="s.value" :label="s.label" :value="s.value" /></el-select></el-form-item>
      <el-form-item label="优先级"><el-select v-model="filters.priority" clearable placeholder="全部"><el-option v-for="p in REQUIREMENT_PRIORITIES" :key="p.value" :label="p.label" :value="p.value" /></el-select></el-form-item>
      <el-form-item label="来源"><el-select v-model="filters.source" clearable placeholder="全部"><el-option label="直接创建" value="DIRECT" /><el-option label="反馈转化" value="FEEDBACK" /></el-select></el-form-item>
      <el-form-item label="版本 ID"><el-input-number v-model="filters.current_version_id" :min="1" :precision="0" step-strictly controls-position="right" /></el-form-item>
      <el-form-item label="负责人 ID"><el-input-number v-model="filters.owner_id" :min="1" :precision="0" step-strictly controls-position="right" /></el-form-item>
    </ListFilterPanel>

    <ErrorState v-if="failed" title="需求加载失败" description="请检查网络后重试。" retry-label="重新加载" @retry="load" />
    <SectionCard v-else title="需求列表" :description="`共 ${total} 条需求`" :padded="false">
    <el-table
      v-if="!isMobile"
      v-loading="loading"
      :data="rows"
      row-key="id"
      @row-click="(row: Requirement) => openDetail(row.id)"
    >
      <el-table-column prop="requirement_no" label="编号" width="180" />
      <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
      <el-table-column prop="priority" label="优先级" width="90" />
      <el-table-column label="来源" width="90">
        <template #default="s">{{ s.row.source === 'FEEDBACK' ? '反馈转化' : '直接创建' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="s">
          <StatusTag
            :status="s.row.status"
            :label="requirementStatusLabel[s.row.status]"
            :type="requirementStatusTagType(s.row.status)"
          />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="s">
          <el-link type="primary" @click.stop="openDetail(s.row.id)">查看</el-link>
        </template>
      </el-table-column>
      <template #empty><EmptyState description="暂无需求" compact /></template>
    </el-table>

    <div v-else v-loading="loading" class="cards">
      <ListCard
        v-for="r in rows"
        :key="r.id"
        :code="r.requirement_no"
        :title="r.title"
        @open="openDetail(r.id)"
      >
        <template #status>
          <StatusTag :status="r.status" :label="requirementStatusLabel[r.status]" :type="requirementStatusTagType(r.status)" size="sm" />
        </template>
          <span>{{ r.priority }}</span>
          <span>{{ r.source === 'FEEDBACK' ? '反馈转化' : '直接创建' }}</span>
      </ListCard>
      <EmptyState v-if="!loading && !rows.length" description="暂无需求" compact />
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
    <el-dialog v-model="createDialog" title="新建需求" class="create-dialog" width="min(720px, calc(100vw - 24px))" destroy-on-close :close-on-click-modal="false">
      <RequirementCreateView v-if="createDialog" embedded @cancel="createDialog = false" @created="onRequirementCreated" />
    </el-dialog>

    <!-- Scheme C: Detail Drawer with full-screen expansion support -->
    <el-drawer
      v-model="detailDrawer"
      title="需求详情"
      direction="rtl"
      size="min(860px, 94vw)"
      destroy-on-close
      class="detail-drawer"
    >
      <template #header>
        <div class="drawer-header-custom">
          <span class="drawer-title">需求详情</span>
          <el-button
            v-if="activeRequirementId"
            size="small"
            class="expand-btn"
            @click="openFullScreen(activeRequirementId)"
          >
            新标签/全屏直达
          </el-button>
        </div>
      </template>
      <RequirementDetailView
        v-if="activeRequirementId && detailDrawer"
        :key="activeRequirementId"
        embedded
        :embedded-id="activeRequirementId"
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
