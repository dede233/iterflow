<script setup lang="ts">
import { computed } from 'vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import { FEEDBACK_STATUSES } from '@/constants/feedback'
import { REQUIREMENT_STATUSES } from '@/constants/requirement'
import { VERSION_STATUSES, versionStatusLabel } from '@/constants/version'
import type { DashboardOverview } from '@/types/dashboard'

const props = defineProps<{ overview: DashboardOverview }>()

const scopeLabel = computed(() => (props.overview.data_scope === 'ALL' ? '全部数据' : '我的数据'))
const allSectionsUnavailable = computed(
  () =>
    props.overview.feedback === null &&
    props.overview.requirements === null &&
    props.overview.versions === null &&
    props.overview.releases === null,
)

const metricCards = computed(() => {
  const cards: { key: string; label: string; value: number; note: string }[] = []
  if (props.overview.feedback) {
    cards.push({
      key: 'feedback',
      label: '待处理反馈',
      value: props.overview.feedback.pending_count,
      note: `共 ${props.overview.feedback.total_count} 条`,
    })
  }
  if (props.overview.requirements) {
    cards.push({
      key: 'requirements',
      label: '进行中需求',
      value: props.overview.requirements.active_count,
      note: `共 ${props.overview.requirements.total_count} 条`,
    })
  }
  if (props.overview.versions) {
    cards.push({
      key: 'versions',
      label: '活跃版本',
      value: props.overview.versions.active_count,
      note: `共 ${props.overview.versions.total_count} 个`,
    })
  }
  if (props.overview.releases) {
    cards.push({
      key: 'releases',
      label: '累计发布',
      value: props.overview.releases.total_count,
      note: '成功发布记录',
    })
  }
  return cards
})

function formatDate(value: string | null): string {
  if (!value) return '未排期'
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium' }).format(new Date(value))
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}
</script>

<template>
  <div>
    <PageHeader title="首页 / 系统概览" description="当前可访问范围内的反馈、需求、版本与发布情况。" eyebrow="工作台">
      <template #actions><span class="scope-chip">{{ scopeLabel }}</span></template>
    </PageHeader>

    <EmptyState
      v-if="allSectionsUnavailable"
      description="当前账号没有可展示的业务概览数据"
    />

    <template v-else>
      <el-row class="metric-grid" :gutter="16">
        <el-col v-for="card in metricCards" :key="card.key" :xs="12" :sm="12" :lg="6">
          <el-card class="metric-card" :class="`metric-card--${card.key}`" shadow="never">
            <div class="metric-index">{{ String(metricCards.indexOf(card) + 1).padStart(2, '0') }} / {{ String(metricCards.length).padStart(2, '0') }}</div>
            <div class="metric-label">{{ card.label }}</div>
            <div class="metric-value">{{ card.value }}</div>
            <div class="metric-note">{{ card.note }}</div>
          </el-card>
        </el-col>
      </el-row>

      <el-row class="section-grid" :gutter="16">
        <el-col v-if="overview.feedback" :xs="24" :lg="12">
          <el-card class="section-card" shadow="never">
            <template #header><strong>反馈状态</strong></template>
            <div class="status-grid">
              <div v-for="status in FEEDBACK_STATUSES" :key="status.value" class="status-item">
                <span>{{ status.label }}</span>
                <strong>{{ overview.feedback.by_status[status.value] ?? 0 }}</strong>
              </div>
            </div>
          </el-card>
        </el-col>

        <el-col v-if="overview.requirements" :xs="24" :lg="12">
          <el-card class="section-card" shadow="never">
            <template #header><strong>需求状态</strong></template>
            <div class="status-grid">
              <div
                v-for="status in REQUIREMENT_STATUSES"
                :key="status.value"
                class="status-item"
              >
                <span>{{ status.label }}</span>
                <strong>{{ overview.requirements.by_status[status.value] ?? 0 }}</strong>
              </div>
            </div>
          </el-card>
        </el-col>

        <el-col v-if="overview.versions" :xs="24" :lg="12">
          <el-card class="section-card" shadow="never">
            <template #header><strong>版本状态</strong></template>
            <div class="status-grid">
              <div v-for="status in VERSION_STATUSES" :key="status.value" class="status-item">
                <span>{{ status.label }}</span>
                <strong>{{ overview.versions.by_status[status.value] ?? 0 }}</strong>
              </div>
            </div>
          </el-card>
        </el-col>

        <el-col v-if="overview.versions" :xs="24" :lg="12">
          <el-card class="section-card recent-card" shadow="never">
            <template #header><strong>近期活跃版本</strong></template>
            <el-empty
              v-if="overview.versions.recent_active_versions.length === 0"
              description="暂无活跃版本"
              :image-size="64"
            />
            <div v-else class="recent-list">
              <router-link
                v-for="version in overview.versions.recent_active_versions"
                :key="version.id"
                :to="`/versions/${version.id}`"
                class="recent-row"
              >
                <div>
                  <div class="recent-title">{{ version.version_no }} · {{ version.name }}</div>
                  <div class="recent-meta">计划发布：{{ formatDate(version.planned_release_date) }}</div>
                </div>
                <StatusTag :status="version.status" :label="versionStatusLabel[version.status] ?? version.status" size="sm" />
              </router-link>
            </div>
          </el-card>
        </el-col>

        <el-col v-if="overview.releases" :xs="24" :lg="12">
          <el-card class="section-card recent-card" shadow="never">
            <template #header>
              <div class="card-header">
                <strong>近期发布</strong>
                <router-link to="/releases" class="more-link">查看全部</router-link>
              </div>
            </template>
            <el-empty
              v-if="overview.releases.recent_releases.length === 0"
              description="暂无发布记录"
              :image-size="64"
            />
            <div v-else class="recent-list">
              <div
                v-for="release in overview.releases.recent_releases"
                :key="release.id"
                class="recent-row"
              >
                <div>
                  <div class="recent-title">{{ release.version_no }} · {{ release.version_name }}</div>
                  <div class="recent-meta">{{ formatDateTime(release.released_at) }}</div>
                </div>
                <StatusTag status="SUCCESS" label="成功" size="sm" />
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<style scoped>
.scope-chip { display: inline-flex; align-items: center; min-height: 30px; padding: 0 12px; border: 1px solid var(--if-brand-100); border-radius: 999px; background: var(--if-brand-50); color: var(--if-brand-700); font-size: 12px; font-weight: 700; }
.metric-grid, .section-grid { row-gap: var(--if-space-4); }
.metric-grid { margin-bottom: var(--if-space-6); }
.metric-card, .section-card { height: 100%; }
.metric-card { position: relative; overflow: hidden; min-height: 162px; background: linear-gradient(145deg, #fff 62%, #f9fbff); }
.metric-card::before { position: absolute; inset: 0 auto 0 0; width: 3px; background: var(--if-brand-500); content: ''; }
.metric-card--feedback::before { background: #eaa344; }
.metric-card--versions::before { background: #7c6ee7; }
.metric-card--releases::before { background: #28a678; }
.metric-index { margin-bottom: 10px; color: var(--if-text-3); font-family: var(--if-font-mono); font-size: 11px; letter-spacing: .06em; }
.metric-label { color: var(--if-text-2); font-size: 13px; font-weight: 600; }
.metric-value { margin: 7px 0 4px; color: var(--if-text-1); font-size: clamp(30px, 3vw, 38px); font-weight: 750; line-height: 1; font-variant-numeric: tabular-nums; }
.metric-note, .recent-meta { color: var(--if-text-3); font-size: 12px; }
.status-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.status-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-width: 0; padding: 10px 12px; border-radius: var(--if-radius-sm); background: var(--if-bg-subtle); color: var(--if-text-2); font-size: 12px; }
.status-item strong { color: var(--if-text-1); font-size: 15px; font-variant-numeric: tabular-nums; }
.card-header, .recent-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-width: 0; }
.more-link { color: var(--if-brand-600); font-size: 12px; font-weight: 600; }
.more-link:hover { text-decoration: underline; }
.recent-list { display: grid; }
.recent-row { min-height: 62px; padding: 10px 2px; border-bottom: 1px solid var(--if-border); }
.recent-row:last-child { border-bottom: 0; }
.recent-row > div { min-width: 0; }
a.recent-row:hover .recent-title { color: var(--if-brand-600); }
.recent-title { margin-bottom: 4px; font-size: 13px; font-weight: 650; overflow-wrap: anywhere; }
@media (max-width: 767px) { .status-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .metric-card { min-height: 140px; } }
</style>
