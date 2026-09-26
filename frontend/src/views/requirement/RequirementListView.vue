<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listRequirements } from '@/api/requirements'
import RequirementCreateView from './RequirementCreateView.vue'
import { useResponsive } from '@/composables/useResponsive'
import { usePermission } from '@/composables/usePermission'
import StatusTag from '@/components/StatusTag.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import ListCard from '@/components/ui/ListCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import { requirementStatusLabel, requirementStatusTagType } from '@/constants/requirement'
import type { Requirement } from '@/types/domain'

const router = useRouter()
const { isMobile } = useResponsive()
const { can } = usePermission()

const rows = ref<Requirement[]>([])
const total = ref(0)
const loading = ref(false)
const failed = ref(false)
const createDialog = ref(false)
const paging = reactive({ page: 1, page_size: 20 })

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    const page = await listRequirements({ page: paging.page, page_size: paging.page_size })
    rows.value = page.items
    total.value = page.total
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

async function onRequirementCreated(id: number): Promise<void> {
  createDialog.value = false
  await load()
  await router.push(`/requirements/${id}`)
}

onMounted(load)
</script>

<template>
  <section class="page">
    <PageHeader title="需求管理" description="从确认、排期到交付，清晰跟进每项研发需求。" eyebrow="研发协作">
      <template #actions>
      <el-button
        v-if="can('rd.requirement.create')"
        type="primary"
        @click="createDialog = true"
      >
        <AppIcon name="plus" :size="16" />新建需求
      </el-button>
      </template>
    </PageHeader>

    <ErrorState v-if="failed" title="需求加载失败" description="请检查网络后重试。" retry-label="重新加载" @retry="load" />
    <SectionCard v-else title="需求列表" :description="`共 ${total} 条需求`" :padded="false">
    <el-table
      v-if="!isMobile"
      v-loading="loading"
      :data="rows"
      row-key="id"
      @row-click="(row: Requirement) => router.push('/requirements/' + row.id)"
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
          <el-link type="primary" @click.stop="router.push('/requirements/' + s.row.id)">查看</el-link>
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
        @open="router.push('/requirements/' + r.id)"
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

    <el-dialog v-model="createDialog" title="新建需求" class="create-dialog" width="min(720px, calc(100vw - 24px))" destroy-on-close :close-on-click-modal="false">
      <RequirementCreateView v-if="createDialog" embedded @cancel="createDialog = false" @created="onRequirementCreated" />
    </el-dialog>
  </section>
</template>

<style scoped>
.cards { display: grid; gap: 8px; padding: var(--if-space-3); }
.pager { margin-top: var(--if-space-4); justify-content: flex-end; }
@media (max-width: 767px) { .pager { justify-content: center; } }
</style>
