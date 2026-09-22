<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listVersions } from '@/api/versions'
import { useResponsive } from '@/composables/useResponsive'
import { usePermission } from '@/composables/usePermission'
import StatusTag from '@/components/StatusTag.vue'
import { versionStatusLabel, versionStatusTagType } from '@/constants/version'
import type { VersionItem } from '@/types/domain'

const router = useRouter()
const { isMobile } = useResponsive()
const { can } = usePermission()

const rows = ref<VersionItem[]>([])
const total = ref(0)
const loading = ref(false)
const paging = reactive({ page: 1, page_size: 20 })

async function load(): Promise<void> {
  loading.value = true
  try {
    const page = await listVersions({ page: paging.page, page_size: paging.page_size })
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
      <h1 class="page-title">版本管理</h1>
      <el-button
        v-if="can('rd.version.create')"
        type="primary"
        @click="router.push('/versions/new')"
      >
        新建版本
      </el-button>
    </div>

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
    </el-table>

    <div v-else v-loading="loading" class="cards">
      <el-card v-for="r in rows" :key="r.id" shadow="never" @click="router.push('/versions/' + r.id)">
        <div class="card-heading">{{ r.version_no }} · {{ r.name }}</div>
        <div class="meta">
          <span>{{ r.planned_release_date || '-' }}</span>
          <StatusTag
            :status="r.status"
            :label="versionStatusLabel[r.status]"
            :type="versionStatusTagType(r.status)"
          />
        </div>
      </el-card>
      <el-empty v-if="!loading && !rows.length" description="暂无版本" />
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
.card-heading { font-weight: 600; margin-bottom: 8px; }
.meta { display: flex; justify-content: space-between; align-items: center; color: #64748b; }
.pager { margin-top: 16px; justify-content: flex-end; }
</style>
