<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listReleases } from '@/api/releases'
import { useResponsive } from '@/composables/useResponsive'
import { usePermission } from '@/composables/usePermission'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import StatusTag from '@/components/StatusTag.vue'
import { formatLocalDateTime } from '@/utils/dates'
import type { ReleaseItem } from '@/types/domain'

const router = useRouter()
const { isMobile } = useResponsive()
const { can } = usePermission()
const rows = ref<ReleaseItem[]>([])
const total = ref(0)
const loading = ref(false)
const failed = ref(false)
const paging = reactive({ page: 1, page_size: 20 })

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    const result = await listReleases({ page: paging.page, page_size: paging.page_size })
    rows.value = result.items
    total.value = result.total
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="page">
    <PageHeader title="发布记录" description="查看版本的实际发布历史与发布说明。" eyebrow="发布" />
    <ErrorState v-if="failed" title="发布记录加载失败" description="请检查网络后重试。" retry-label="重新加载" @retry="load" />
    <SectionCard v-else title="发布历史" :description="`共 ${total} 次发布`" :padded="false">
      <el-table v-if="!isMobile" v-loading="loading" :data="rows" row-key="id">
        <el-table-column prop="version_id" label="版本 ID" width="120" />
        <el-table-column label="发布时间" width="210">
          <template #default="s">{{ formatLocalDateTime(s.row.released_at) }}</template>
        </el-table-column>
        <el-table-column label="结果" width="120">
          <template #default="s"><StatusTag :status="s.row.result" label="成功" /></template>
        </el-table-column>
        <el-table-column prop="release_notes" label="发布说明" min-width="260" show-overflow-tooltip />
        <el-table-column v-if="can('rd.version.view')" label="操作" width="100" fixed="right">
          <template #default="s"><el-button link type="primary" @click="router.push('/versions/' + s.row.version_id)">查看版本</el-button></template>
        </el-table-column>
        <template #empty><EmptyState description="暂无发布记录" compact /></template>
      </el-table>
      <div v-else v-loading="loading" class="cards">
        <article v-for="release in rows" :key="release.id" class="release-card">
          <div class="release-card-top"><span class="mono">版本 #{{ release.version_id }}</span><StatusTag :status="release.result" label="成功" size="sm" /></div>
          <div class="release-time">{{ formatLocalDateTime(release.released_at) }}</div>
          <p>{{ release.release_notes }}</p>
          <el-button v-if="can('rd.version.view')" link type="primary" @click="router.push('/versions/' + release.version_id)">查看版本</el-button>
        </article>
        <EmptyState v-if="!loading && !rows.length" description="暂无发布记录" compact />
      </div>
    </SectionCard>
    <el-pagination class="pager" layout="prev, pager, next, total" :total="total" :current-page="paging.page" :page-size="paging.page_size" background @current-change="(page: number) => { paging.page = page; void load() }" />
  </section>
</template>

<style scoped>
.cards { display: grid; gap: 8px; padding: var(--if-space-3); }
.release-card { min-width: 0; padding: 14px; border: 1px solid var(--if-border); border-radius: var(--if-radius); background: var(--if-bg-surface); }
.release-card-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.release-time { margin-top: 8px; color: var(--if-text-2); font-size: 12px; }
.release-card p { margin: 10px 0; font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }
.pager { margin-top: var(--if-space-4); justify-content: flex-end; }
@media (max-width: 767px) { .pager { justify-content: center; } }
</style>
