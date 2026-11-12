<script setup lang="ts">
import BatchActionsDialog from '@/components/BatchActionsDialog.vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { listFeedbacks } from '@/api/feedbacks'
import FeedbackCreateView from './FeedbackCreateView.vue'
import FeedbackDetailView from './FeedbackDetailView.vue'
import { listSystems } from '@/api/systems'
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
import { feedbackFilterChips } from '@/utils/appliedListFilters'
import {
  FEEDBACK_STATUSES,
  FEEDBACK_TYPES,
  FEEDBACK_URGENCIES,
  feedbackStatusLabel,
  feedbackStatusTagType,
  feedbackTypeLabel,
  feedbackUrgencyLabel,
} from '@/constants/feedback'
import type {
  BusinessSystemItem,
  Feedback,
  FeedbackListParams,
} from '@/types/domain'

const router = useRouter()
const route = useRoute()
const { isMobile } = useResponsive()
const { can } = usePermission()

const rows = ref<Feedback[]>([])
const total = ref(0)
const loading = ref(false)
const failed = ref(false)
const filterDrawer = ref(false)
const createDialog = ref(false)
const createSaving = ref(false)
const createFormRef = ref<InstanceType<typeof FeedbackCreateView>>()
watch(createDialog, open => { if (!open) createSaving.value = false })
async function beforeCreateClose(done: () => void): Promise<void> {
  if (!createSaving.value && (await createFormRef.value?.requestClose() ?? false)) done()
}
const detailDrawer = ref(false)
const activeFeedbackId = ref<number | null>(null)
const systems = ref<BusinessSystemItem[]>([])
const canReadSystems = computed(() => can(['sys.system.view', 'sys.system.manage']))

const filters = reactive({
  keyword: '',
  status: '' as FeedbackListParams['status'],
  feedback_type: '' as FeedbackListParams['feedback_type'],
  urgency: '' as FeedbackListParams['urgency'],
  system_id: null as number | null,
  page: 1,
  page_size: 20,
})

const activeFilters = computed(() => feedbackFilterChips(route.query, systems.value, canReadSystems.value))
const advancedCount = computed(() => activeFilters.value.filter(f => ['feedback_type', 'urgency'].includes(f.key)).length)
function removeFilter(key: string) {
  const query: typeof route.query = { ...route.query, page: '1' }
  delete query[key]
  void router.push({ path: '/feedbacks', query })
}

let requestSequence = 0
let disposed = false
onBeforeUnmount(() => { disposed = true; requestSequence++ })

async function load(): Promise<void> {
  const q = queryState.applied()
  const current = { page: Number(q.page ?? 1), page_size: Number(q.page_size ?? 20), keyword: q.keyword ?? '', status: q.status as FeedbackListParams['status'], feedback_type: q.feedback_type as FeedbackListParams['feedback_type'], urgency: q.urgency as FeedbackListParams['urgency'], system_id: q.system_id ? Number(q.system_id) : null }

  if (disposed) return
  const sequence = ++requestSequence
  loading.value = true
  failed.value = false
  try {
    const page = await listFeedbacks({
      page: current.page,
      page_size: current.page_size,
      keyword: current.keyword.trim() || undefined,
      status: current.status || undefined,
      feedback_type: current.feedback_type || undefined,
      urgency: current.urgency || undefined,
      system_id: current.system_id ?? undefined,
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

function systemName(id: number | null | undefined): string {
  if (!id) return '-'
  return systems.value.find((s) => s.id === id)?.name ?? `#${id}`
}

function openDetail(id: number): void {
  activeFeedbackId.value = id
  detailDrawer.value = true
}

function openFullScreen(id: number): void {
  detailDrawer.value = false
  void router.push(queryState.detail(`/feedbacks/${id}`))
}

async function onFeedbackCreated(id: number): Promise<void> {
  createDialog.value = false
  await load()
  await router.push(queryState.detail(`/feedbacks/${id}`))
}

onMounted(async () => {
  if (canReadSystems.value) {
    try {
      const data = await listSystems()
      if (disposed) return
      systems.value = data.systems
    } catch {
      // System dictionary is optional for filtering; ignore if unavailable.
    }
  }
})

const queryState = useListQuery({
  path: '/feedbacks', readDraft: () => ({ ...filters }),
  restore: q => {
    filters.page = Number(q.page ?? 1)
    filters.page_size = Number(q.page_size ?? 20)
    filters.keyword = (q.keyword ?? '') as typeof filters.keyword
    filters.status = (q.status ?? '') as typeof filters.status
    filters.feedback_type = (q.feedback_type ?? '') as typeof filters.feedback_type
    filters.urgency = (q.urgency ?? '') as typeof filters.urgency
    filters.system_id = q.system_id ? Number(q.system_id) : null
  },
  load, invalidate: () => { requestSequence++ },
})
</script>

<template>
  <section class="page">
    <PageHeader title="反馈中心" description="收集、受理并追踪每一条反馈。" eyebrow="研发协作">
      <template #actions>
      <BatchActionsDialog kind="feedbacks" :rows="rows" @updated="load" />
        <el-button v-if="isMobile" @click="filterDrawer = true"><AppIcon name="filter" :size="16" />筛选</el-button>
        <el-button
          v-if="can('rd.feedback.create')"
          type="primary"
          @click="createDialog = true"
        >
          <AppIcon name="plus" :size="16" />提交反馈
        </el-button>
      </template>
    </PageHeader>

    <ListFilterPanel v-model="filterDrawer" :mobile="isMobile" title="筛选反馈" :advanced-count="advancedCount" @search="applyFilters" @reset="resetFilters">
      <el-form-item v-if="canReadSystems" label="业务系统">
        <el-select v-model="filters.system_id" clearable placeholder="全部系统"><el-option v-for="s in systems" :key="s.id" :label="s.name" :value="s.id" /></el-select>
      </el-form-item>
      <el-form-item label="关键词"><el-input v-model="filters.keyword" placeholder="编号 / 标题 / 描述" :maxlength="200" clearable @keyup.enter="applyFilters" /></el-form-item>
      <el-form-item label="状态"><el-select v-model="filters.status" clearable placeholder="全部"><el-option v-for="s in FEEDBACK_STATUSES" :key="s.value" :label="s.label" :value="s.value" /></el-select></el-form-item>
      <template #advanced>
        <el-form-item label="类型"><el-select v-model="filters.feedback_type" clearable placeholder="全部"><el-option v-for="t in FEEDBACK_TYPES" :key="t.value" :label="t.label" :value="t.value" /></el-select></el-form-item>
        <el-form-item label="紧急度"><el-select v-model="filters.urgency" clearable placeholder="全部"><el-option v-for="u in FEEDBACK_URGENCIES" :key="u.value" :label="u.label" :value="u.value" /></el-select></el-form-item>
      </template>
    </ListFilterPanel>
    <div v-if="activeFilters.length" class="active-filters" aria-label="已应用筛选"><span>当前筛选</span><el-tag v-for="filter in activeFilters" :key="filter.key" closable @close="removeFilter(filter.key)">{{ filter.label }}</el-tag></div>

    <ErrorState v-if="failed" title="反馈加载失败" description="请检查网络后重试。" retry-label="重新加载" @retry="load" />
    <SectionCard v-else title="反馈列表" :description="`共 ${total} 条反馈`" :padded="false">
    <!-- Desktop table -->
    <el-table
      v-if="!isMobile"
      v-loading="loading"
      :data="rows"
      row-key="id"
      @row-click="(row: Feedback) => openDetail(row.id)"
    >
      <el-table-column label="反馈" min-width="280"><template #default="s"><button class="record-title" @click.stop="openDetail(s.row.id)">{{ s.row.title }}</button><div class="mono record-code">{{ s.row.feedback_no }}</div></template></el-table-column>
      <el-table-column label="类型" width="120">
        <template #default="s">{{ feedbackTypeLabel[s.row.feedback_type] ?? s.row.feedback_type }}</template>
      </el-table-column>
      <el-table-column label="紧急度" width="90">
        <template #default="s">{{ feedbackUrgencyLabel[s.row.urgency] ?? s.row.urgency }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="s">
          <StatusTag
            :status="s.row.status"
            :label="feedbackStatusLabel[s.row.status]"
            :type="feedbackStatusTagType(s.row.status)"
          />
        </template>
      </el-table-column>
      <el-table-column v-if="canReadSystems" label="系统" width="140">
        <template #default="s">{{ systemName(s.row.system_id) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="s">
          <el-link type="primary" @click.stop="openDetail(s.row.id)">查看</el-link>
        </template>
      </el-table-column>
      <template #empty><EmptyState description="暂无反馈" compact /></template>
    </el-table>

    <!-- Mobile cards -->
    <div v-else v-loading="loading" class="cards">
      <ListCard v-for="r in rows" :key="r.id" :code="r.feedback_no" :title="r.title" @open="openDetail(r.id)">
        <template #status>
          <StatusTag :status="r.status" :label="feedbackStatusLabel[r.status]" :type="feedbackStatusTagType(r.status)" size="sm" />
        </template>
          <span>{{ feedbackTypeLabel[r.feedback_type] ?? r.feedback_type }}</span>
          <span>{{ feedbackUrgencyLabel[r.urgency] ?? r.urgency }}</span>
      </ListCard>
      <EmptyState v-if="!loading && !rows.length" description="暂无反馈" compact />
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
    <el-dialog v-model="createDialog" title="提交反馈" class="create-dialog" width="min(860px, calc(100vw - 24px))" destroy-on-close :close-on-click-modal="false" :before-close="beforeCreateClose" :show-close="!createSaving" :close-on-press-escape="!createSaving">
      <FeedbackCreateView v-if="createDialog" ref="createFormRef" embedded @cancel="createDialog = false" @created="onFeedbackCreated" @saving="createSaving = $event" />
    </el-dialog>

    <!-- Scheme C: Detail Drawer with full-screen expansion support -->
    <el-drawer
      v-model="detailDrawer"
      title="反馈详情"
      direction="rtl"
      :size="isMobile ? '100%' : 'min(860px, 94vw)'"
      destroy-on-close
      class="detail-drawer"
    >
      <template #header>
        <div class="drawer-header-custom">
          <span class="drawer-title">反馈详情</span>
          <el-button
            v-if="activeFeedbackId"
            size="small"
            class="expand-btn"
            @click="openFullScreen(activeFeedbackId)"
          >
            打开完整页面
          </el-button>
        </div>
      </template>
      <FeedbackDetailView
        v-if="activeFeedbackId && detailDrawer"
        :key="activeFeedbackId"
        embedded
        :embedded-id="activeFeedbackId"
        @updated="load"
        @close="detailDrawer = false"
      />
    </el-drawer>
  </section>
</template>

<style scoped>
.active-filters { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: -4px 0 16px; color: var(--if-text-secondary); font-size: 13px; }
.record-title { display: block; border: 0; padding: 4px 0; background: transparent; color: var(--if-text-primary); font: inherit; font-size: 14px; font-weight: 600; text-align: left; cursor: pointer; overflow-wrap: anywhere; }
.record-title:hover { color: var(--if-brand-600); }
.record-code { margin-top: 2px; }
.cards { display: grid; gap: 8px; padding: var(--if-space-3); }
.pager { margin-top: var(--if-space-4); justify-content: flex-end; }
.drawer-header-custom { display: flex; align-items: center; justify-content: space-between; width: 100%; padding-right: 28px; }
.drawer-title { font-size: 16px; font-weight: 600; color: var(--if-text-primary); }
.expand-btn { margin-left: auto; }
@media (max-width: 767px) { .pager { justify-content: center; } }
</style>
