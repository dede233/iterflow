<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listRequirements } from '@/api/requirements'
import { useResponsive } from '@/composables/useResponsive'
import { usePermission } from '@/composables/usePermission'
import StatusTag from '@/components/StatusTag.vue'
import { requirementStatusLabel, requirementStatusTagType } from '@/constants/requirement'
import type { Requirement } from '@/types/domain'

const router = useRouter()
const { isMobile } = useResponsive()
const { can } = usePermission()

const rows = ref<Requirement[]>([])
const total = ref(0)
const loading = ref(false)
const paging = reactive({ page: 1, page_size: 20 })

async function load(): Promise<void> {
  loading.value = true
  try {
    const page = await listRequirements({ page: paging.page, page_size: paging.page_size })
    rows.value = page.items
    total.value = page.total
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="page">
    <div class="head">
      <h1 class="page-title">需求管理</h1>
      <el-button
        v-if="can('rd.requirement.create')"
        type="primary"
        @click="router.push('/requirements/new')"
      >
        新建需求
      </el-button>
    </div>

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
    </el-table>

    <div v-else v-loading="loading" class="cards">
      <el-card
        v-for="r in rows"
        :key="r.id"
        shadow="never"
        @click="router.push('/requirements/' + r.id)"
      >
        <div class="card-title">{{ r.requirement_no }}</div>
        <div class="card-heading">{{ r.title }}</div>
        <div class="meta">
          <span>{{ r.priority }}</span>
          <StatusTag
            :status="r.status"
            :label="requirementStatusLabel[r.status]"
            :type="requirementStatusTagType(r.status)"
          />
        </div>
      </el-card>
      <el-empty v-if="!loading && !rows.length" description="暂无需求" />
    </div>

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
  </section>
</template>

<style scoped>
.head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
.cards { display: grid; gap: 10px; }
.cards .el-card { cursor: pointer; }
.card-title { font-size: 12px; color: #94a3b8; }
.card-heading { font-weight: 600; margin: 2px 0 8px; }
.meta { display: flex; justify-content: space-between; align-items: center; color: #64748b; }
.pager { margin-top: 16px; justify-content: flex-end; }
</style>
