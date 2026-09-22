<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listFeedbacks } from '@/api/feedbacks'
import { listSystems } from '@/api/systems'
import { useResponsive } from '@/composables/useResponsive'
import { usePermission } from '@/composables/usePermission'
import StatusTag from '@/components/StatusTag.vue'
import {
  FEEDBACK_STATUSES,
  FEEDBACK_TYPES,
  FEEDBACK_URGENCIES,
  feedbackStatusLabel,
  feedbackStatusTagType,
  feedbackTypeLabel,
  feedbackUrgencyLabel,
} from '@/constants/feedback'
import type { BusinessModuleItem, BusinessSystemItem, Feedback } from '@/types/domain'

const router = useRouter()
const { isMobile } = useResponsive()
const { can } = usePermission()

const rows = ref<Feedback[]>([])
const total = ref(0)
const loading = ref(false)
const filterDrawer = ref(false)
const systems = ref<BusinessSystemItem[]>([])
const modules = ref<BusinessModuleItem[]>([])
const canReadSystems = computed(() => can('sys.system.view'))

const filters = reactive({
  keyword: '',
  status: '',
  feedback_type: '',
  urgency: '',
  system_id: null as number | null,
  module_id: null as number | null,
  page: 1,
  page_size: 20,
})

const moduleOptions = computed(() =>
  filters.system_id ? modules.value.filter((m) => m.system_id === filters.system_id) : [],
)

async function load(): Promise<void> {
  loading.value = true
  try {
    const page = await listFeedbacks({
      page: filters.page,
      page_size: filters.page_size,
      keyword: filters.keyword.trim() || undefined,
      status: filters.status || undefined,
      feedback_type: filters.feedback_type || undefined,
      urgency: filters.urgency || undefined,
      system_id: filters.system_id ?? undefined,
      module_id: filters.module_id ?? undefined,
    })
    rows.value = page.items
    total.value = page.total
  } finally {
    loading.value = false
  }
}

function applyFilters(): void {
  filters.page = 1
  filterDrawer.value = false
  void load()
}

function resetFilters(): void {
  Object.assign(filters, {
    keyword: '',
    status: '',
    feedback_type: '',
    urgency: '',
    system_id: null,
    module_id: null,
    page: 1,
  })
  void load()
}

function onSystemChange(): void {
  filters.module_id = null
}

function systemName(id: number | null | undefined): string {
  if (!id) return '-'
  return systems.value.find((s) => s.id === id)?.name ?? `#${id}`
}

onMounted(async () => {
  if (canReadSystems.value) {
    try {
      const data = await listSystems()
      systems.value = data.systems
      modules.value = data.modules
    } catch {
      // System dictionary is optional for filtering; ignore if unavailable.
    }
  }
  await load()
})
</script>

<template>
  <section class="page">
    <div class="head">
      <div>
        <h1 class="page-title">反馈中心</h1>
        <p class="hint">按你的数据范围展示反馈。</p>
      </div>
      <div class="head-actions">
        <el-button v-if="isMobile" @click="filterDrawer = true">筛选</el-button>
        <el-button
          v-if="can('rd.feedback.create')"
          type="primary"
          @click="router.push('/feedbacks/new')"
        >
          提交反馈
        </el-button>
      </div>
    </div>

    <!-- Desktop filter bar -->
    <el-form v-if="!isMobile" class="filters" :inline="true">
      <el-form-item label="关键词">
        <el-input
          v-model="filters.keyword"
          placeholder="编号/标题/描述"
          clearable
          style="width: 200px"
          @keyup.enter="applyFilters"
        />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.status" clearable placeholder="全部" style="width: 130px">
          <el-option v-for="s in FEEDBACK_STATUSES" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="filters.feedback_type" clearable placeholder="全部" style="width: 130px">
          <el-option v-for="t in FEEDBACK_TYPES" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="紧急度">
        <el-select v-model="filters.urgency" clearable placeholder="全部" style="width: 110px">
          <el-option v-for="u in FEEDBACK_URGENCIES" :key="u.value" :label="u.label" :value="u.value" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="canReadSystems" label="系统">
        <el-select
          v-model="filters.system_id"
          clearable
          placeholder="全部"
          style="width: 140px"
          @change="onSystemChange"
        >
          <el-option v-for="s in systems" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="canReadSystems && filters.system_id" label="模块">
        <el-select v-model="filters.module_id" clearable placeholder="全部" style="width: 140px">
          <el-option v-for="m in moduleOptions" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="applyFilters">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </el-form-item>
    </el-form>

    <!-- Desktop table -->
    <el-table
      v-if="!isMobile"
      v-loading="loading"
      :data="rows"
      row-key="id"
      @row-click="(row: Feedback) => router.push('/feedbacks/' + row.id)"
    >
      <el-table-column prop="feedback_no" label="编号" width="180" />
      <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
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
          <el-link type="primary" @click.stop="router.push('/feedbacks/' + s.row.id)">查看</el-link>
        </template>
      </el-table-column>
    </el-table>

    <!-- Mobile cards -->
    <div v-else v-loading="loading" class="cards">
      <el-card v-for="r in rows" :key="r.id" shadow="never" @click="router.push('/feedbacks/' + r.id)">
        <div class="card-title">{{ r.feedback_no }}</div>
        <div class="card-heading">{{ r.title }}</div>
        <div class="meta">
          <span>{{ feedbackTypeLabel[r.feedback_type] ?? r.feedback_type }}</span>
          <StatusTag
            :status="r.status"
            :label="feedbackStatusLabel[r.status]"
            :type="feedbackStatusTagType(r.status)"
          />
        </div>
      </el-card>
      <el-empty v-if="!loading && !rows.length" description="暂无反馈" />
    </div>

    <el-pagination
      class="pager"
      layout="prev, pager, next, total"
      :total="total"
      :current-page="filters.page"
      :page-size="filters.page_size"
      background
      @current-change="
        (p: number) => {
          filters.page = p
          load()
        }
      "
    />

    <!-- Mobile filter drawer -->
    <el-drawer v-model="filterDrawer" title="筛选" direction="rtl" size="80%">
      <el-form label-position="top">
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="编号/标题/描述" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width: 100%">
            <el-option v-for="s in FEEDBACK_STATUSES" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="filters.feedback_type" clearable placeholder="全部" style="width: 100%">
            <el-option v-for="t in FEEDBACK_TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="紧急度">
          <el-select v-model="filters.urgency" clearable placeholder="全部" style="width: 100%">
            <el-option v-for="u in FEEDBACK_URGENCIES" :key="u.value" :label="u.label" :value="u.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetFilters">重置</el-button>
        <el-button type="primary" @click="applyFilters">查询</el-button>
      </template>
    </el-drawer>
  </section>
</template>

<style scoped>
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.hint { margin: -8px 0 16px; color: #64748b; font-size: 13px; }
.head-actions { display: flex; gap: 8px; }
.filters { margin-bottom: 8px; }
.cards { display: grid; gap: 10px; }
.cards .el-card { cursor: pointer; }
.card-title { font-size: 12px; color: #94a3b8; }
.card-heading { font-weight: 600; margin: 2px 0 8px; }
.meta { display: flex; justify-content: space-between; align-items: center; color: #64748b; }
.pager { margin-top: 16px; justify-content: flex-end; }
</style>
