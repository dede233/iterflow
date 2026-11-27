<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAdProduction, listAdProductions, type AdProduction } from '@/api/adProductions'
import AppIcon from '@/components/ui/AppIcon.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import ListCard from '@/components/ui/ListCard.vue'
import ListFilterPanel from '@/components/ui/ListFilterPanel.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import RichTextContent from '@/components/RichTextContent.vue'
import { useListQuery } from '@/composables/useListQuery'
import { usePermission } from '@/composables/usePermission'
import { useResponsive } from '@/composables/useResponsive'
import { AD_PRODUCTION_LABELS, AD_PRODUCTION_PERMISSIONS, AD_PRODUCTION_PUBLISHER_LABEL, AD_PRODUCTION_STATUSES, MERCHANT_AD_STATUSES, adProductionStatusDisplay, type AdProductionKind, type AdProductionStatus } from '@/constants/adProduction'
import { formatLocalDateTime } from '@/utils/dates'
import AdProductionEditor from './AdProductionEditor.vue'
import AdProductionImage from './AdProductionImage.vue'
import { adProductionTitle, designerName, publisherName } from './adProductionDisplay'

const props = defineProps<{ kind: AdProductionKind }>()
const route = useRoute()
const router = useRouter()
const labels = computed(() => AD_PRODUCTION_LABELS[props.kind])
const isMerchantAd = computed(() => props.kind === 'MERCHANT_AD')
const statusOptions = computed(() => isMerchantAd.value ? MERCHANT_AD_STATUSES : AD_PRODUCTION_STATUSES)
const path = isMerchantAd.value ? '/merchant-ads' : '/ad-productions'
const { isMobile, isTablet } = useResponsive()
const useCards = computed(() => isMobile.value || isTablet.value)
const { can } = usePermission()
const permissions = computed(() => AD_PRODUCTION_PERMISSIONS[props.kind])
const canView = computed(() => can(permissions.value.view))
const canCreate = computed(() => canView.value && can(permissions.value.create))
const canEdit = computed(() => canView.value && can(permissions.value.edit))
const rows = shallowRef<AdProduction[]>([])
const total = ref(0)
const loading = ref(true)
const listFailed = ref(false)
const listKindMismatch = ref(false)
const filterDrawer = ref(false)
const filterError = ref('')
const appliedFilterCount = ref(0)
const filters = reactive({
  page: 1, page_size: 20, keyword: '', status: '' as AdProductionStatus | '', date_from: '', date_to: '',
})
let listSequence = 0

function matchesKind(record: AdProduction): boolean {
  return (record.kind ?? 'MATERIAL') === props.kind
}

function parseStatus(value: string | undefined): AdProductionStatus | undefined {
  return statusOptions.value.find(option => option.value === value)?.value
}

function localDayBoundary(day?: string, nextDay = false): string | undefined {
  if (!day) return undefined
  const boundary = new Date(`${day}T00:00:00`)
  if (nextDay) boundary.setDate(boundary.getDate() + 1)
  return boundary.toISOString()
}

async function loadList(): Promise<void> {
  const query = queryState.applied()
  const sequence = ++listSequence
  loading.value = true
  listFailed.value = false
  try {
    const result = await listAdProductions({
      kind: props.kind,
      page: Number(query.page ?? 1),
      page_size: Number(query.page_size ?? 20),
      keyword: query.keyword,
      status: parseStatus(query.status),
      published_from: localDayBoundary(query.date_from),
      published_before: localDayBoundary(query.date_to, true),
    })
    if (sequence !== listSequence) return
    listKindMismatch.value = result.items.some(item => !matchesKind(item))
    if (listKindMismatch.value) {
      rows.value = []
      total.value = 0
      listFailed.value = true
      return
    }
    rows.value = result.items
    total.value = result.total
  } catch {
    if (sequence === listSequence) listFailed.value = true
  } finally {
    if (sequence === listSequence) loading.value = false
  }
}

const queryState = useListQuery({
  path,
  readDraft: () => ({ ...filters }),
  restore: query => {
    filters.page = Number(query.page ?? 1)
    filters.page_size = Number(query.page_size ?? 20)
    filters.keyword = query.keyword ?? ''
    filters.status = parseStatus(query.status) ?? ''
    filters.date_from = query.date_from ?? ''
    filters.date_to = query.date_to ?? ''
    filterError.value = ''
    appliedFilterCount.value = [filters.keyword, filters.status, filters.date_from || filters.date_to].filter(Boolean).length
  },
  load: loadList,
  invalidate: () => { listSequence++ },
})

function applyFilters(): void {
  if (filters.date_from && filters.date_to && filters.date_from > filters.date_to) {
    filterError.value = '开始日期须早于或等于结束日期。'
    return
  }
  filterDrawer.value = false
  void queryState.apply()
}

function resetFilters(): void {
  filterDrawer.value = false
  void queryState.reset()
}

const record = shallowRef<AdProduction | null>(null)
const selected = ref<{ id: number; edit: boolean } | null>(null)
const detailOpen = ref(false)
const detailLoading = ref(false)
const detailFailed = ref(false)
const editorOpen = ref(false)
const editorStatusOnly = ref(false)
const editorRecord = shallowRef<AdProduction | null>(null)
const status = computed(() => record.value ? adProductionStatusDisplay(props.kind, record.value.status) : null)
const linkedRecordId = computed(() => {
  const value = route.path === path ? route.query.record_id : null
  if (typeof value !== 'string' || !/^\d+$/.test(value)) return null
  const id = Number(value)
  return Number.isSafeInteger(id) && id > 0 ? id : null
})
let detailRequest: AbortController | undefined

function openEditor(value: AdProduction | null, statusOnly = false): void {
  if (value ? !canEdit.value : !canCreate.value || loading.value || listKindMismatch.value) return
  if (!statusOnly) {
    detailOpen.value = false
    resetDetail()
  }
  editorStatusOnly.value = statusOnly
  editorRecord.value = value
  editorOpen.value = true
}

function resetDetail(): void {
  detailRequest?.abort()
  selected.value = null
  record.value = null
  detailLoading.value = false
  detailFailed.value = false
}

function closeDetail(): void {
  resetDetail()
  if (linkedRecordId.value === null) return
  const query = { ...route.query }
  delete query.record_id
  void router.replace({ path, query })
}

async function loadDetail(): Promise<void> {
  const target = selected.value
  if (!target) return
  detailRequest?.abort()
  const request = new AbortController()
  detailRequest = request
  detailLoading.value = true
  detailFailed.value = false
  try {
    const result = await getAdProduction(target.id, request.signal)
    if (request.signal.aborted) return
    if (!matchesKind(result)) {
      detailFailed.value = true
      return
    }
    if (target.edit) openEditor(result)
    else record.value = result
  } catch {
    if (!request.signal.aborted) detailFailed.value = true
  } finally {
    if (!request.signal.aborted) detailLoading.value = false
  }
}

function openRecord(id: number, edit = false): void {
  resetDetail()
  selected.value = { id, edit }
  detailOpen.value = true
  void loadDetail()
}

function afterSave(saved: AdProduction): void {
  if (editorStatusOnly.value) record.value = saved
  editorOpen.value = false
  void loadList()
}

watch(linkedRecordId, (id, previous) => {
  if (id !== null && id !== selected.value?.id) openRecord(id)
  else if (id === null && previous === selected.value?.id) detailOpen.value = false
}, { immediate: true })

onBeforeUnmount(() => detailRequest?.abort())
</script>

<template>
  <section class="page" data-testid="ad-production-list">
    <PageHeader :title="labels.name">
      <template #actions>
        <el-button v-if="isMobile" @click="filterDrawer = true"><AppIcon name="filter" :size="16" />筛选{{ appliedFilterCount ? ` (${appliedFilterCount})` : '' }}</el-button>
        <el-button v-if="canCreate" :disabled="loading || listKindMismatch" type="primary" data-testid="ad-production-create" @click="openEditor(null)"><AppIcon name="plus" :size="16" />发布{{ labels.name }}需求</el-button>
      </template>
    </PageHeader>

    <ListFilterPanel v-model="filterDrawer" class="ad-production-filters" :mobile="isMobile" :title="`筛选${labels.name}需求`" @search="applyFilters" @reset="resetFilters">
      <el-form-item class="filter-field" label="关键词" for="ad-production-filter-keyword">
        <el-input id="ad-production-filter-keyword" v-model="filters.keyword" data-testid="ad-production-filter-keyword" placeholder="搜索标题或内容" :maxlength="100" clearable @keyup.enter="applyFilters" />
      </el-form-item>
      <el-form-item class="filter-field" label="状态" for="ad-production-filter-status">
        <el-select
          id="ad-production-filter-status"
          v-model="filters.status"
          data-testid="ad-production-filter-status"
          placeholder="全部"
          clearable
          value-on-clear=""
        >
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item class="filter-field" label="发布起始日期" for="ad-production-filter-date-from">
        <el-date-picker
          id="ad-production-filter-date-from"
          v-model="filters.date_from"
          data-testid="ad-production-filter-date-from"
          type="date"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          placeholder="选择开始日期"
          popper-class="list-filter-date-popper"
          value-on-clear=""
        />
      </el-form-item>
      <el-form-item class="filter-field" label="发布结束日期" for="ad-production-filter-date-to">
        <el-date-picker
          id="ad-production-filter-date-to"
          v-model="filters.date_to"
          data-testid="ad-production-filter-date-to"
          type="date"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          placeholder="选择结束日期"
          popper-class="list-filter-date-popper"
          value-on-clear=""
        />
      </el-form-item>
      <p v-if="filterError" class="filter-error" role="alert">{{ filterError }}</p>
    </ListFilterPanel>

    <ErrorState
      v-if="listFailed"
      :title="`${labels.name}记录加载失败`"
      :description="listKindMismatch ? '服务返回的记录类型与当前页面不符。请联系管理员检查接口版本，修复后重新加载。' : undefined"
      retry-label="重新加载"
      @retry="loadList"
    />
    <SectionCard v-else :title="`${labels.name}需求`" :description="`共 ${total} 条`" :padded="false">
      <el-table
        v-if="!useCards"
        v-loading="loading"
        :data="rows"
        row-key="id"
        :aria-label="`${labels.name}记录`"
        @row-click="(row: AdProduction) => openRecord(row.id)"
      >
        <el-table-column label="标题" min-width="172">
          <template #default="{ row }">
            <button type="button" class="record-title" @click.stop="openRecord(row.id)">{{ adProductionTitle(row) }}</button>
          </template>
        </el-table-column>
        <el-table-column label="发布时间" min-width="140">
          <template #default="{ row }"><time :datetime="row.created_at">{{ formatLocalDateTime(row.created_at) }}</time></template>
        </el-table-column>
        <el-table-column label="截止时间" min-width="140">
          <template #default="{ row }"><time v-if="row.due_at" :datetime="row.due_at">{{ formatLocalDateTime(row.due_at) }}</time><span v-else>—</span></template>
        </el-table-column>
        <el-table-column label="需求接收人" min-width="104">
          <template #default="{ row }">{{ designerName(row, 'receiver_id') }}</template>
        </el-table-column>
        <el-table-column label="状态" width="96">
          <template #default="{ row }"><StatusTag :status="row.status" :label="adProductionStatusDisplay(kind, row.status).label" :type="adProductionStatusDisplay(kind, row.status).tone" /></template>
        </el-table-column>
        <el-table-column label="图片" width="72">
          <template #default="{ row }"><span class="image-count">{{ row.images.length ? `${row.images.length} 张` : '—' }}</span></template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" :width="canEdit ? 116 : 90">
          <template #default="{ row }">
            <el-button link type="primary" :data-testid="`ad-production-view-${row.id}`" @click.stop="openRecord(row.id)">查看</el-button>
            <el-button v-if="canEdit" link type="primary" :data-testid="`ad-production-edit-${row.id}`" @click.stop="openRecord(row.id, true)">编辑</el-button>
          </template>
        </el-table-column>
        <template #empty><EmptyState v-if="!loading" :description="`暂无${labels.name}记录`" compact /></template>
      </el-table>
      <div v-else v-loading="loading" class="record-cards">
        <ListCard
          v-for="row in rows"
          :key="row.id"
          :code="`发布时间 ${formatLocalDateTime(row.created_at)}`"
          :title="adProductionTitle(row)"
          :data-testid="`ad-production-card-${row.id}`"
          class="record-card"
          @open="openRecord(row.id)"
        >
          <template #status>
            <StatusTag :status="row.status" :label="adProductionStatusDisplay(kind, row.status).label" :type="adProductionStatusDisplay(kind, row.status).tone" size="sm" />
          </template>
          <template #default>
            <span>需求接收人 {{ designerName(row, 'receiver_id') }}</span>
            <span>截止时间 <time v-if="row.due_at" :datetime="row.due_at">{{ formatLocalDateTime(row.due_at) }}</time><template v-else>—</template></span>
            <span v-if="row.images.length">{{ row.images.length }} 张图片</span>
          </template>
        </ListCard>
        <EmptyState v-if="!loading && !rows.length" :description="`暂无${labels.name}记录`" compact />
      </div>
    </SectionCard>
    <el-pagination
      v-if="!listFailed && total > filters.page_size"
      class="pager"
      layout="prev, pager, next"
      :pager-count="isMobile ? 5 : 7"
      :total="total"
      :current-page="filters.page"
      :page-size="filters.page_size"
      background
      @current-change="queryState.paginate"
    />

    <el-drawer
      v-model="detailOpen"
      append-to-body
      destroy-on-close
      class="detail-drawer"
      :title="selected?.edit ? `编辑${labels.name}需求` : `${labels.name}详情`"
      direction="rtl"
      :size="isMobile ? '100%' : 'min(680px, 94vw)'"
      :close-on-press-escape="!editorOpen"
      :close-on-click-modal="!editorOpen"
      @close="closeDetail"
    >
      <div class="record-detail" data-testid="ad-production-detail">
        <p v-if="detailLoading" role="status" class="loading-detail">正在加载记录…</p>
        <ErrorState v-else-if="detailFailed" :title="`${labels.name}记录加载失败`" retry-label="重新加载" @retry="loadDetail" />
        <template v-else-if="record && status">
          <SectionCard>
            <h2 class="detail-title">{{ adProductionTitle(record) }}</h2>
            <dl class="detail-meta">
              <div><dt>{{ AD_PRODUCTION_PUBLISHER_LABEL }}</dt><dd>{{ publisherName(record) }}</dd></div>
              <div><dt>需求接收人</dt><dd>{{ designerName(record, 'receiver_id') }}</dd></div>
              <div><dt>发布时间</dt><dd><time :datetime="record.created_at">{{ formatLocalDateTime(record.created_at) }}</time></dd></div>
              <div><dt>截止时间</dt><dd><time v-if="record.due_at" :datetime="record.due_at">{{ formatLocalDateTime(record.due_at) }}</time><template v-else>—</template></dd></div>
              <div><dt>状态</dt><dd><StatusTag :status="record.status" :label="status.label" :type="status.tone" /></dd></div>
              <div v-if="record.status === 'COMPLETED'"><dt>实际完成人</dt><dd>{{ designerName(record, 'completed_by_id') }}</dd></div>
            </dl>
            <div class="detail-content">
              <h3>需求内容</h3>
              <RichTextContent :ad-production-id="record.id" :content="record.content" :format="record.content_format" />
            </div>
            <div v-if="isMerchantAd && record.status === 'COMPLETED' && record.processing_result" class="detail-content">
              <h3>处理结果</h3>
              <p class="processing-result">{{ record.processing_result }}</p>
            </div>
          </SectionCard>
          <SectionCard title="图片">
            <div v-if="record.images.length" class="ad-image-grid">
              <AdProductionImage v-for="image in record.images" :key="image.file_id" :source="{ recordId: record.id, fileId: image.file_id, name: image.original_name }" />
            </div>
            <p v-else class="no-images">暂无图片</p>
          </SectionCard>
        </template>
      </div>
      <template #footer>
        <div class="detail-footer">
          <el-button @click="detailOpen = false">关闭</el-button>
          <el-button v-if="record && canEdit" data-testid="ad-production-detail-edit" @click="openEditor(record)">编辑</el-button>
          <el-button v-if="record && canEdit" type="primary" data-testid="ad-production-change-status" @click="openEditor(record, true)">更改状态</el-button>
        </div>
      </template>
    </el-drawer>
    <AdProductionEditor
      v-if="editorOpen"
      v-model="editorOpen"
      :kind="kind"
      :record="editorRecord"
      :mobile="isMobile"
      :status-only="editorStatusOnly"
      @saved="afterSave"
      @reloaded="record = $event"
    />
  </section>
</template>

<style scoped>
.processing-result { margin: 0; overflow-wrap: anywhere; white-space: pre-wrap; }
.ad-production-filters :deep(.filter-fields:has(.el-date-editor)) {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 224px), 1fr));
}
.ad-production-filters :deep(.el-form-item:has(.el-date-editor) .el-form-item__label) {
  flex-basis: 96px;
  width: 96px;
}
.filter-error { grid-column: 1 / -1; margin: 0; color: var(--el-color-danger); }
.record-title {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  border: 0;
  padding: 4px 0;
  background: transparent;
  color: var(--if-text-primary);
  cursor: pointer;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  text-align: left;
  white-space: pre-line;
  overflow-wrap: anywhere;
  line-height: 1.5;
}
.record-title:hover { color: var(--if-brand-600); }
.image-count { color: var(--if-text-secondary); }
.record-cards { display: grid; gap: var(--if-space-2); min-height: 96px; padding: var(--if-space-3); }
.record-card { min-width: 0; }
.record-card :deep(.list-card__title) {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  white-space: pre-line;
}
.pager { margin-top: var(--if-space-4); justify-content: flex-end; }
.record-detail { container-type: inline-size; }
.detail-title { margin: 0 0 var(--if-space-4); font-size: 18px; overflow-wrap: anywhere; }
.detail-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--if-space-3); margin: 0 0 var(--if-space-4); }
.detail-meta dt { margin-bottom: 4px; color: var(--if-text-secondary); font-size: 12px; }
.detail-meta dd { min-height: 22px; margin: 0; overflow-wrap: anywhere; }
.detail-content { padding-top: var(--if-space-4); border-top: 1px solid var(--if-border); }
.detail-content h3 { margin: 0 0 var(--if-space-2); font-size: 14px; }
.ad-image-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 108px), 1fr)); gap: var(--if-space-3); }
.no-images, .loading-detail { margin: 0; color: var(--if-text-secondary); }
.detail-footer { display: flex; flex-wrap: wrap; gap: var(--if-space-2); }
.detail-footer .el-button + .el-button { margin-left: 0; }
@container (max-width: 420px) {
  .detail-meta { grid-template-columns: minmax(0, 1fr); }
}
@media (min-width: 768px) and (max-width: 1199px) {
  .record-cards { grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr)); }
}
@media (max-width: 767px) {
  .filter-field :deep(.el-input__wrapper), .filter-field :deep(.el-select__wrapper) { min-height: 44px; }
  .filter-field :deep(.el-input__inner) { font-size: 16px; }
  .pager { justify-content: center; }
  .pager :deep(button), .pager :deep(.el-pager li) { min-height: 44px; min-width: 40px; }
  .detail-footer { width: 100%; padding-bottom: env(safe-area-inset-bottom); }
  .detail-footer .el-button { flex: 1; min-height: 44px; }
}
</style>
