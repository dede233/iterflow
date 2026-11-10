<script setup lang="ts">
import { computed, ref } from 'vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import { FEEDBACK_STATUSES } from '@/constants/feedback'
import { REQUIREMENT_STATUSES } from '@/constants/requirement'
import { VERSION_STATUSES, versionStatusLabel } from '@/constants/version'
import { auditActionLabel, auditEntityLabel } from '@/utils/auditLabels'
import type { DashboardActivityEntityType, DashboardOverview } from '@/types/dashboard'

const props = defineProps<{ overview: DashboardOverview; viewerId?: number }>()
const expandedActivity = ref(false)
const visibleActivities = computed(() => expandedActivity.value ? props.overview.activities : props.overview.activities.slice(0, 5))

const scopeLabel = computed(() => (props.overview.data_scope === 'ALL' ? '全部数据' : '我的数据'))
const activityRoutes: Record<DashboardActivityEntityType, string> = {
  FEEDBACK: '/feedbacks',
  REQUIREMENT: '/requirements',
  VERSION: '/versions',
  RELEASE: '/releases',
}
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

    <nav v-if="overview.requirements && viewerId" class="work-shortcuts" aria-label="我的协作入口">
      <router-link :to="`/requirements?status=DRAFT&participant_id=${viewerId}&participant_role=CONFIRM`"><span>内容确认</span><strong>查看待我确认的需求 <span aria-hidden="true">→</span></strong></router-link>
      <router-link :to="`/requirements?status=CONFIRMED&participant_id=${viewerId}&participant_role=DEVELOP`"><span>开发准备</span><strong>查看待我开发的需求 <span aria-hidden="true">→</span></strong></router-link>
      <router-link :to="`/requirements?status=TESTING&participant_id=${viewerId}&participant_role=ACCEPT`"><span>交付验收</span><strong>查看待我验收的需求 <span aria-hidden="true">→</span></strong></router-link>
    </nav>
    <EmptyState
      v-if="allSectionsUnavailable"
      description="当前账号没有可展示的业务概览数据"
    />

    <template v-else>
      <el-row class="metric-grid" :gutter="16">
        <el-col v-for="card in metricCards" :key="card.key" :xs="12" :sm="12" :lg="6">
          <el-card class="metric-card" :class="`metric-card--${card.key}`" shadow="never">
            <div class="metric-label">{{ card.label }}</div>
            <div class="metric-value">{{ card.value }}</div>
            <div class="metric-note">{{ card.note }}</div>
          </el-card>
        </el-col>
      </el-row>

      <el-row class="section-grid" :gutter="16">
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
      <details class="dashboard-distribution"><summary>查看各阶段数量</summary>
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

      </el-row>
      </details>
    </template>

    <el-card class="section-card activity-card" shadow="never">
      <template #header><strong>最近活动</strong></template>
      <EmptyState v-if="overview.activities.length === 0" description="暂无最近活动" compact />
      <div v-else class="recent-list">
        <router-link
          v-for="(activity, index) in visibleActivities"
          :key="index"
          :to="`${activityRoutes[activity.entity_type]}/${activity.entity_id}`"
          class="recent-row activity-row"
        >
          <div class="activity-description">
            <span class="recent-title">{{ auditEntityLabel(activity.entity_type) }} #{{ activity.entity_id }}</span>
            <span class="activity-action">{{ auditActionLabel(activity.action) }}</span>
          </div>
          <time class="recent-meta" :datetime="activity.created_at">{{ formatDateTime(activity.created_at) }}</time>
        </router-link>
      </div>
      <button v-if="overview.activities.length > 5" class="activity-toggle" :aria-expanded="expandedActivity" @click="expandedActivity = !expandedActivity">{{ expandedActivity ? '收起活动' : `展开最近 ${overview.activities.length} 条活动` }}</button>
    </el-card>
  </div>
</template>

<style scoped>
.work-shortcuts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 0 0 24px; }
.work-shortcuts a { display: grid; gap: 8px; padding: 18px; border: 1px solid var(--if-brand-100); border-radius: 8px; background: var(--if-brand-50); }
.work-shortcuts a > span { font-size: 12px; color: var(--if-text-tertiary); }
.work-shortcuts strong { display: flex; justify-content: space-between; gap: 8px; color: var(--if-brand-700); font-size: 14px; }
.work-shortcuts a:hover { border-color: var(--if-brand-400); }
.dashboard-distribution { margin-top: 16px; }
.dashboard-distribution > summary { cursor: pointer; padding: 12px 0; color: var(--if-text-secondary); font-size: 13px; }
.activity-toggle { margin-top: 12px; padding: 8px 0; min-height: 44px; border: 0; background: transparent; color: var(--if-brand-600); font: inherit; font-size: 13px; cursor: pointer; }
@media (max-width: 767px) { .work-shortcuts { grid-template-columns: 1fr; gap: 8px; } .work-shortcuts a { padding: 12px 16px; } }

.scope-chip { display: inline-flex; align-items: center; min-height: 30px; padding: 0 12px; border: 1px solid var(--if-brand-100); border-radius: 999px; background: var(--if-brand-50); color: var(--if-brand-700); font-size: 12px; font-weight: 700; }
.metric-grid, .section-grid { row-gap: var(--if-space-4); }
.metric-grid { margin-bottom: var(--if-space-6); }
.metric-card, .section-card { height: 100%; }
.metric-card { position: relative; overflow: hidden; min-height: 126px; background: var(--if-bg-surface); }
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
.activity-card { margin-top: var(--if-space-4); }
.activity-description { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; }
.activity-description .recent-title { margin-bottom: 0; }
.activity-action { color: var(--if-text-2); font-size: 13px; overflow-wrap: anywhere; }
.activity-row { text-decoration: none; border-radius: var(--if-radius-sm); padding: 12px 8px; }
.activity-row:hover, .activity-row:focus-visible { background: var(--if-bg-subtle); }
.activity-row time { flex-shrink: 0; }
@media (max-width: 767px) { .status-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .metric-card { min-height: 126px; } }
@media (max-width: 767px) { .activity-row { flex-direction: column; align-items: flex-start; gap: 6px; } }
</style>
