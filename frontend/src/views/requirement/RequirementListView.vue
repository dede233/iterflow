<script setup lang="ts">
import BusinessSystemSelect from '@/components/BusinessSystemSelect.vue'
import BatchActionsDialog from '@/components/BatchActionsDialog.vue'
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
import ListEntityFilterSelect from '@/components/ListEntityFilterSelect.vue'
import { REQUIREMENT_PRIORITIES, REQUIREMENT_STATUSES, requirementStatusLabel, requirementStatusTagType } from '@/constants/requirement'
import type { Requirement, RequirementListParams } from '@/types/domain'

function handlerNames(row: Requirement) { return row.current_handlers?.map(p => p.display_name).join('、') || (['DONE', 'ONLINE', 'CANCELED'].includes(row.status) ? '—' : '待分配') }
const router = useRouter()
const route = useRoute()
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
const filters = reactive({ system_id: null as number | null, page: 1, page_size: 20, keyword: '', status: '' as RequirementListParams['status'], priority: '' as RequirementListParams['priority'], source: '' as RequirementListParams['source'], current_version_id: null as number | null, participant_id: null as number | null, participant_role: '' as RequirementListParams['participant_role'] })
const filterLabels: Record<string, string> = { system_id: '业务系统', keyword: '关键词', status: '状态', priority: '优先级', source: '来源', current_version_id: '版本', participant_id: '参与人', participant_role: '环节角色' }
const activeFilters = computed(() => Object.entries(route.query).filter(([key, value]) => filterLabels[key] && typeof value === 'string' && value).map(([key, value]) => ({ key, label: `${filterLabels[key]}：${key.endsWith('_id') ? '已指定' : key === 'status' ? requirementStatusLabel[String(value)] || value : key === 'source' ? (value === 'DIRECT' ? '直接创建' : '反馈转化') : key === 'participant_role' ? ({ CONFIRM: '确认人', DESIGN: '设计人员', DEVELOP: '开发人员', ACCEPT: '验收人' } as Record<string, string>)[String(value)] || value : value}` })))
const advancedCount = computed(() => activeFilters.value.filter(f => !['system_id', 'keyword', 'status'].includes(f.key)).length)
function removeFilter(key: string) {
  const query = { ...route.query }
  query.page = '1'
  delete query[key]
  void router.push({ path: '/requirements', query })
}
let requestSequence = 0
const positiveId = (value: number | null) => value != null && Number.isSafeInteger(value) && value >= 1 ? value : undefined

async function load(): Promise<void> {
  const q = queryState.applied()
  const current = { system_id: q.system_id ? Number(q.system_id) : null, page: Number(q.page ?? 1), page_size: Number(q.page_size ?? 20), keyword: q.keyword ?? '', status: q.status as RequirementListParams['status'], priority: q.priority as RequirementListParams['priority'], source: q.source as RequirementListParams['source'], current_version_id: q.current_version_id ? Number(q.current_version_id) : null, participant_id: q.participant_id ? Number(q.participant_id) : null, participant_role: q.participant_role as RequirementListParams['participant_role'] }

  const sequence = ++requestSequence
  loading.value = true
  failed.value = false
  try {
    const page = await listRequirements({
      system_id: current.system_id || undefined,
      page: current.page, page_size: current.page_size,
      keyword: current.keyword.trim() || undefined, status: current.status || undefined,
      priority: current.priority || undefined, source: current.source || undefined,
      current_version_id: positiveId(current.current_version_id), participant_id: positiveId(current.participant_id), participant_role: current.participant_role || undefined,
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
    filters.system_id = q.system_id ? Number(q.system_id) : null
    filters.page = Number(q.page ?? 1)
    filters.page_size = Number(q.page_size ?? 20)
    filters.keyword = (q.keyword ?? '') as typeof filters.keyword
    filters.status = (q.status ?? '') as typeof filters.status
    filters.priority = (q.priority ?? '') as typeof filters.priority
    filters.source = (q.source ?? '') as typeof filters.source
    filters.current_version_id = q.current_version_id ? Number(q.current_version_id) : null
    filters.participant_role = q.participant_role as RequirementListParams['participant_role']
    filters.participant_id = q.participant_id ? Number(q.participant_id) : null
  },
  load, invalidate: () => { requestSequence++ },
})
</script>

<template>
  <section class="page">
    <PageHeader title="需求管理" description="从确认、开发到交付，清晰跟进每项研发需求。" eyebrow="研发协作">
      <template #actions>
      <BatchActionsDialog kind="requirements" :rows="rows" @updated="load" />
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

    <ListFilterPanel v-model="filterDrawer" :mobile="isMobile" title="筛选需求" :advanced-count="advancedCount" @search="applyFilters" @reset="resetFilters">
      <el-form-item label="业务系统"><BusinessSystemSelect v-model="filters.system_id" /></el-form-item>
      <el-form-item label="关键词"><el-input v-model="filters.keyword" placeholder="编号 / 标题" :maxlength="200" clearable @keyup.enter="applyFilters" /></el-form-item>
      <el-form-item label="状态"><el-select v-model="filters.status" clearable placeholder="全部"><el-option v-for="s in REQUIREMENT_STATUSES" :key="s.value" :label="s.label" :value="s.value" /></el-select></el-form-item>
      <template #advanced>
      <el-form-item label="优先级"><el-select v-model="filters.priority" clearable placeholder="全部"><el-option v-for="p in REQUIREMENT_PRIORITIES" :key="p.value" :label="p.label" :value="p.value" /></el-select></el-form-item>
      <el-form-item label="来源"><el-select v-model="filters.source" clearable placeholder="全部"><el-option label="直接创建" value="DIRECT" /><el-option label="反馈转化" value="FEEDBACK" /></el-select></el-form-item>
      <el-form-item label="版本"><ListEntityFilterSelect v-model="filters.current_version_id" kind="requirement-version" label="版本" /></el-form-item>
      <el-form-item label="参与人"><ListEntityFilterSelect v-model="filters.participant_id" kind="participant" label="参与人" /></el-form-item>
      <el-form-item label="环节角色"><el-select v-model="filters.participant_role" clearable><el-option label="确认人" value="CONFIRM" /><el-option label="设计人员" value="DESIGN" /><el-option label="开发人员" value="DEVELOP" /><el-option label="验收人" value="ACCEPT" /></el-select></el-form-item>
      </template>
    </ListFilterPanel>
    <div v-if="activeFilters.length" class="active-filters" aria-label="已应用筛选"><span>当前筛选</span><el-tag v-for="filter in activeFilters" :key="filter.key" closable @close="removeFilter(filter.key)">{{ filter.label }}</el-tag></div>

    <ErrorState v-if="failed" title="需求加载失败" description="请检查网络后重试。" retry-label="重新加载" @retry="load" />
    <SectionCard v-else :title="`需求列表 · ${total}`" :padded="false">
    <el-table
      v-if="!isMobile"
      v-loading="loading"
      :data="rows"
      row-key="id"
      @row-click="(row: Requirement) => openDetail(row.id)"
    >
      <el-table-column label="需求" min-width="280"><template #default="s"><button class="record-title" @click.stop="openDetail(s.row.id)">{{ s.row.title }}</button><div class="mono record-code">{{ s.row.requirement_no }}</div></template></el-table-column>
      <el-table-column label="业务系统" min-width="130"><template #default="scope">{{ scope.row.system_name || '未指定' }}</template></el-table-column>
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
      <el-table-column label="当前待处理人" min-width="150"><template #default="s">{{ handlerNames(s.row) }}</template></el-table-column>
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
          <span>{{ r.system_name || '未指定系统' }}</span>
          <span>{{ r.current_handlers?.map(p => p.display_name).join('、') || '暂无待处理人员' }}</span>
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
    <el-dialog v-model="createDialog" title="新建需求" class="create-dialog" width="min(1040px, calc(100vw - 32px))" destroy-on-close :close-on-click-modal="false">
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
        @close="detailDrawer = false"
      />
    </el-drawer>
  </section>
</template>

<style scoped>
.active-filters { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: -4px 0 16px; color: var(--if-text-secondary); font-size: 12px; }
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
