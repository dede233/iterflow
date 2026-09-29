<script setup lang="ts">
import { formatLocalDateTime } from '@/utils/dates'
import type { ConflictSummaryRow, RevisionConflictData } from '@/types/revisionConflict'

defineProps<{
  visible: boolean
  loading: boolean
  entityLabel: string
  submittedRevision: number | string | null
  metadata: RevisionConflictData | null
  summary: ConflictSummaryRow[]
  readError: string
}>()

defineEmits<{ close: []; reload: [] }>()
</script>

<template>
  <el-dialog
    :model-value="visible"
    append-to-body
    title="数据已被其他用户修改"
    width="min(560px, calc(100vw - 32px))"
    :close-on-click-modal="false"
    @close="$emit('close')"
  >
    <p class="conflict-intro">{{ entityLabel }}已更新。你的输入仍保留在原表单中，可关闭提示后复制或人工核对。</p>
    <dl class="conflict-meta">
      <div><dt>你的 revision</dt><dd>{{ submittedRevision ?? '-' }}</dd></div>
      <div><dt>服务器 revision</dt><dd>{{ metadata?.current_revision ?? '-' }}</dd></div>
      <div><dt>最后更新时间</dt><dd>{{ formatLocalDateTime(metadata?.current_updated_at) }}</dd></div>
      <div><dt>最后更新人</dt><dd>{{ metadata?.current_updated_by == null ? '-' : `用户 #${metadata.current_updated_by}` }}</dd></div>
    </dl>
    <div class="conflict-summary" aria-label="服务器最新摘要">
      <h3>服务器最新摘要</h3>
      <p v-if="readError" class="conflict-error" role="alert">{{ readError }}</p>
      <p v-else-if="loading && !summary.length">正在读取服务器版本…</p>
      <dl v-else>
        <div v-for="row in summary" :key="row.label"><dt>{{ row.label }}</dt><dd>{{ row.value || '-' }}</dd></div>
      </dl>
    </div>
    <template #footer>
      <el-button @click="$emit('close')">关闭并人工处理</el-button>
      <el-button type="primary" :loading="loading" @click="$emit('reload')">重新加载服务器版本</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.conflict-intro { margin: 0 0 16px; color: var(--if-text-2); line-height: 1.6; overflow-wrap: anywhere; }
.conflict-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0 0 18px; }
.conflict-meta > div, .conflict-summary dl > div { min-width: 0; }
dt { color: var(--if-text-3); font-size: 12px; }
dd { margin: 4px 0 0; color: var(--if-text-1); overflow-wrap: anywhere; white-space: pre-wrap; }
.conflict-summary { padding: 14px; border: 1px solid var(--if-border); border-radius: var(--if-radius-sm); background: var(--if-bg-subtle); }
.conflict-summary h3 { margin: 0 0 12px; font-size: 14px; }
.conflict-summary dl { display: grid; gap: 10px; margin: 0; }
.conflict-error { color: var(--el-color-danger); }
@media (max-width: 480px) { .conflict-meta { grid-template-columns: 1fr; } }
</style>
