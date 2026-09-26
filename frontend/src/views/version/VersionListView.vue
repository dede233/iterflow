<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listVersions } from '@/api/versions'
import VersionCreateView from './VersionCreateView.vue'
import { useResponsive } from '@/composables/useResponsive'
import { usePermission } from '@/composables/usePermission'
import StatusTag from '@/components/StatusTag.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import ListCard from '@/components/ui/ListCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import { versionStatusLabel, versionStatusTagType } from '@/constants/version'
import type { VersionItem } from '@/types/domain'

const router = useRouter()
const { isMobile } = useResponsive()
const { can } = usePermission()

const rows = ref<VersionItem[]>([])
const total = ref(0)
const loading = ref(false)
const failed = ref(false)
const createDialog = ref(false)
const paging = reactive({ page: 1, page_size: 20 })

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    const page = await listVersions({ page: paging.page, page_size: paging.page_size })
    rows.value = page.items
    total.value = page.total
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

async function onVersionCreated(id: number): Promise<void> {
  createDialog.value = false
  await load()
  await router.push(`/versions/${id}`)
}

onMounted(load)
</script>

<template>
  <section class="page">
    <PageHeader title="版本管理" description="规划版本范围、跟踪进度并准备发布。" eyebrow="研发协作">
      <template #actions>
      <el-button
        v-if="can('rd.version.create')"
        type="primary"
        @click="createDialog = true"
      >
        <AppIcon name="plus" :size="16" />新建版本
      </el-button>
      </template>
    </PageHeader>

    <ErrorState v-if="failed" title="版本加载失败" description="请检查网络后重试。" retry-label="重新加载" @retry="load" />
    <SectionCard v-else title="版本列表" :description="`共 ${total} 个版本`" :padded="false">
    <el-table
      v-if="!isMobile"
      v-loading="loading"
      :data="rows"
      row-key="id"
      @row-click="(row: VersionItem) => router.push('/versions/' + row.id)"
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
          <el-link type="primary" @click.stop="router.push('/versions/' + s.row.id)">查看</el-link>
        </template>
      </el-table-column>
      <template #empty><EmptyState description="暂无版本" compact /></template>
    </el-table>

    <div v-else v-loading="loading" class="cards">
      <ListCard v-for="r in rows" :key="r.id" :code="r.version_no" :title="r.name" @open="router.push('/versions/' + r.id)">
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
      :current-page="paging.page"
      :page-size="paging.page_size"
      background
      @current-change="
        (p: number) => {
          paging.page = p
          load()
        }
      "
    />

    <el-dialog v-model="createDialog" title="新建版本" class="create-dialog" width="min(720px, calc(100vw - 24px))" destroy-on-close :close-on-click-modal="false">
      <VersionCreateView v-if="createDialog" embedded @cancel="createDialog = false" @created="onVersionCreated" />
    </el-dialog>
  </section>
</template>

<style scoped>
.cards { display: grid; gap: 8px; padding: var(--if-space-3); }
.pager { margin-top: var(--if-space-4); justify-content: flex-end; }
@media (max-width: 767px) { .pager { justify-content: center; } }
</style>
