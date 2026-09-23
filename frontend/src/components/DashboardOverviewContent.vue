<script setup lang="ts">
import { computed } from 'vue'
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
    <div class="overview-heading">
      <div>
        <h1>首页 / 系统概览</h1>
        <p>聚焦当前可访问范围内的反馈、需求、版本与发布情况。</p>
      </div>
      <el-tag effect="plain" type="info">{{ scopeLabel }}</el-tag>
    </div>

    <el-empty
      v-if="allSectionsUnavailable"
      description="当前账号没有可展示的业务概览数据"
      :image-size="88"
    />

    <template v-else>
      <el-row class="metric-grid" :gutter="16">
        <el-col v-for="card in metricCards" :key="card.key" :xs="12" :sm="12" :lg="6">
          <el-card class="metric-card" shadow="never">
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
                <el-tag effect="plain">{{ versionStatusLabel[version.status] ?? version.status }}</el-tag>
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
                <el-tag type="success" effect="plain">成功</el-tag>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<style scoped>
.overview-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.overview-heading h1 {
  margin: 0;
  font-size: 24px;
}

.overview-heading p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 14px;
}

.metric-grid,
.section-grid {
  row-gap: 16px;
}

.metric-grid {
  margin-bottom: 16px;
}

.metric-card,
.section-card {
  height: 100%;
  border-color: #e5eaf1;
}

.metric-label,
.metric-note,
.recent-meta {
  color: #64748b;
}

.metric-label {
  font-size: 14px;
}

.metric-value {
  margin: 8px 0 4px;
  color: #0f172a;
  font-size: 30px;
  font-weight: 700;
  line-height: 1.2;
}

.metric-note,
.recent-meta {
  font-size: 12px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.status-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f8fafc;
  color: #475569;
  font-size: 13px;
}

.status-item strong {
  color: #0f172a;
  font-size: 16px;
}

.card-header,
.recent-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.more-link {
  color: #2563eb;
  font-size: 13px;
}

.recent-list {
  display: grid;
  gap: 2px;
}

.recent-row {
  min-height: 56px;
  padding: 8px 4px;
  border-bottom: 1px solid #eef2f6;
}

.recent-row:last-child {
  border-bottom: 0;
}

a.recent-row:hover {
  color: #2563eb;
}

.recent-title {
  margin-bottom: 5px;
  font-size: 14px;
  font-weight: 600;
}

@media (max-width: 767px) {
  .overview-heading h1 {
    font-size: 20px;
  }

  .overview-heading p {
    display: none;
  }

  .status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
