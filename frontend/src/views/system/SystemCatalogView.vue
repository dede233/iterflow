<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { isAxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import {
  createSystem,
  listManagedSystems,
  updateSystem,
} from '@/api/systems'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useResponsive } from '@/composables/useResponsive'
import type { BusinessSystemItem } from '@/types/domain'

type Editor = { item: BusinessSystemItem | null }

const { isMobile } = useResponsive()
const systems = ref<BusinessSystemItem[]>([])
const loading = ref(false)
const failed = ref(false)
const saving = ref(false)
const editor = ref<Editor | null>(null)
const form = reactive({ code: '', name: '', sort_order: 0, enabled: true })

const dialogVisible = computed({
  get: () => editor.value !== null,
  set: (visible: boolean) => { if (!visible) editor.value = null },
})
const dialogTitle = computed(() => {
  if (!editor.value) return ''
  return `${editor.value.item ? '编辑' : '创建'}系统`
})

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    const catalog = await listManagedSystems()
    systems.value = catalog.systems
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

function openCreateSystem(): void {
  Object.assign(form, { code: '', name: '', sort_order: 0, enabled: true })
  editor.value = { item: null }
}

function openEditSystem(item: BusinessSystemItem): void {
  Object.assign(form, item)
  editor.value = { item }
}

async function save(): Promise<void> {
  const current = editor.value
  if (!current || saving.value) return
  const code = form.code.trim()
  const name = form.name.trim()
  if (!code || !name) {
    ElMessage.warning('请填写编码和名称')
    return
  }
  saving.value = true
  try {
    const values = { code, name, sort_order: form.sort_order, enabled: form.enabled }
    if (current.item) {
      await updateSystem(current.item.id, { ...values, revision: current.item.revision })
    } else {
      await createSystem(values)
    }
    editor.value = null
    ElMessage.success('设置已保存')
    await load()
  } catch (error) {
    if (isAxiosError(error) && error.response?.status === 409) {
      editor.value = null
      await load()
    } else {
      ElMessage.error('保存失败，请检查输入或稍后重试')
    }
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="page">
    <PageHeader title="业务系统" description="维护业务系统的名称、编码和启停状态。" eyebrow="系统设置">
      <template #actions><el-button type="primary" @click="openCreateSystem">创建系统</el-button></template>
    </PageHeader>
    <ErrorState v-if="failed" title="系统设置加载失败" description="请检查网络后重试。" retry-label="重新加载" @retry="load" />
    <template v-else>
      <SectionCard title="业务系统" :description="`共 ${systems.length} 个系统 · 停用后不再出现在新反馈中`" :padded="false">
        <el-table v-if="!isMobile" v-loading="loading" :data="systems" row-key="id">
          <el-table-column prop="name" label="系统名称" min-width="180" />
          <el-table-column prop="code" label="编码" min-width="150" />
          <el-table-column label="状态" width="100">
            <template #default="scope"><StatusTag :status="scope.row.enabled ? 'ENABLED' : 'DISABLED'" :label="scope.row.enabled ? '启用' : '停用'" /></template>
          </el-table-column>
          <el-table-column prop="sort_order" label="排序" width="80" />
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="scope">
              <el-button link type="primary" :aria-label="`编辑系统 ${scope.row.name}`" @click="openEditSystem(scope.row)">编辑</el-button>
            </template>
          </el-table-column>
          <template #empty><EmptyState description="暂无系统，先创建一个业务系统" compact /></template>
        </el-table>
        <div v-else v-loading="loading" class="mobile-list">
          <article v-for="system in systems" :key="system.id" class="catalog-card">
            <div class="catalog-card__head"><div><strong>{{ system.name }}</strong><span class="catalog-code">{{ system.code }}</span></div><StatusTag :status="system.enabled ? 'ENABLED' : 'DISABLED'" :label="system.enabled ? '启用' : '停用'" size="sm" /></div>
            <div class="catalog-card__meta">排序 {{ system.sort_order }}</div>
            <div class="catalog-card__actions"><el-button :aria-label="`编辑系统 ${system.name}`" @click="openEditSystem(system)">编辑</el-button></div>
          </article>
          <EmptyState v-if="!loading && !systems.length" description="暂无系统，先创建一个业务系统" compact />
        </div>
      </SectionCard>
    </template>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="min(560px, 92vw)" append-to-body destroy-on-close>
      <el-form label-position="top" @submit.prevent="save">
        <el-row :gutter="16">
          <el-col :xs="24" :sm="12"><el-form-item label="编码" required><el-input v-model="form.code" maxlength="64" placeholder="如 ITERFLOW" /></el-form-item></el-col>
          <el-col :xs="24" :sm="12"><el-form-item label="名称" required><el-input v-model="form.name" maxlength="100" placeholder="输入名称" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :xs="24" :sm="12"><el-form-item label="排序"><el-input-number v-model="form.sort_order" :min="0" controls-position="right" style="width: 100%" /></el-form-item></el-col>
          <el-col :xs="24" :sm="12"><el-form-item label="状态"><el-switch v-model="form.enabled" active-text="启用" inactive-text="停用" /></el-form-item></el-col>
        </el-row>
        <p class="dialog-hint">停用后不再供新反馈选择，已有反馈和需求的历史关联会保留。</p>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.mobile-list { display: grid; gap: 10px; padding: 16px; }
.catalog-card { min-width: 0; padding: 14px; border: 1px solid var(--if-border); border-radius: var(--if-radius); background: var(--if-bg-surface); }
.catalog-card__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.catalog-card__head strong { display: block; font-size: 15px; }
.catalog-code { display: block; margin-top: 3px; color: var(--if-text-3); font-family: var(--if-font-mono); font-size: 12px; overflow-wrap: anywhere; }
.catalog-card__meta { margin-top: 10px; color: var(--if-text-2); font-size: 12px; }
.catalog-card__actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.catalog-card__actions :deep(.el-button + .el-button) { margin-left: 0; }
.dialog-hint { margin: 4px 0 0; color: var(--if-text-3); font-size: 12px; line-height: 1.5; }
@media (max-width: 767px) { .mobile-list { padding: 12px; } }
</style>
