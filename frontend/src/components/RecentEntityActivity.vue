<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { listEntityActivities, type ActivityKind } from '@/api/entityActivities'
import { useAuthStore } from '@/stores/auth'
import { auditActionLabel } from '@/utils/auditLabels'
import { formatLocalDateTime } from '@/utils/dates'
import type { EntityActivity } from '@/types/domain'

const props = defineProps<{ kind: ActivityKind; id: number; revision?: number; refreshKey?: number }>()
const auth = useAuthStore()
const items = ref<EntityActivity[]>([])
const loading = ref(false)
const failed = ref(false)
const expanded = ref(false)
const retry = ref(0)
let sequence = 0
const identity = computed(() => `${auth.user?.id}:${auth.accessToken}:${auth.permissionCodes.join(',')}`)
const actor = (item: EntityActivity) => item.operator?.display_name || item.operator?.username || '系统操作 / 操作人未记录'

watch(() => [props.kind, props.id, props.revision, props.refreshKey, identity.value, retry.value] as const, async () => {
  const current = ++sequence
  items.value = []
  failed.value = false
  loading.value = false
  if (!auth.hasPermission(`rd.${props.kind}.view`)) return
  loading.value = true
  try {
    const result = await listEntityActivities(props.kind, props.id)
    if (current === sequence) items.value = result.slice(0, 10)
  } catch {
    if (current === sequence) failed.value = true
  } finally {
    if (current === sequence) loading.value = false
  }
}, { immediate: true, flush: 'sync' })
watch(() => [props.kind, props.id, identity.value], () => { expanded.value = false })
onScopeDispose(() => { sequence++ })
</script>

<template>
  <section class="recent-activity" aria-label="最近操作">
    <header>
      <div class="activity-summary">
        <strong>最近操作人</strong>
        <span v-if="loading" role="status">正在加载…</span>
        <span v-else-if="failed" role="alert">操作记录暂时无法加载 <el-button link type="primary" @click="retry++">重试</el-button></span>
        <template v-else-if="items[0]">
          <span>{{ actor(items[0]) }}</span>
          <span class="activity-meta">{{ auditActionLabel(items[0].action) }} · {{ formatLocalDateTime(items[0].created_at) }}</span>
        </template>
        <span v-else>暂无操作记录</span>
      </div>
      <el-button v-if="items.length" link type="primary" :aria-expanded="expanded" @click="expanded = !expanded">{{ expanded ? '收起操作记录' : '查看最近 10 条操作' }}</el-button>
    </header>
    <ol v-if="expanded && items.length" aria-label="最近10条操作记录">
      <li v-for="entry in items" :key="entry.id">
        <div><strong>{{ actor(entry) }}</strong><span>{{ auditActionLabel(entry.action) }}</span></div>
        <time :datetime="entry.created_at">{{ formatLocalDateTime(entry.created_at) }}</time>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.recent-activity { margin-top: 16px; border: 1px solid var(--if-border); border-radius: var(--if-radius); background: var(--if-bg-surface); padding: 12px 16px; min-width: 0; overflow-wrap: anywhere; }
header { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px 16px; flex-wrap: wrap; }
.activity-summary { display: flex; align-items: baseline; flex-wrap: wrap; gap: 6px 12px; font-size: 13px; min-width: 0; }
.activity-summary > strong { font-weight: 500; }
.activity-meta, time { font-size: 12px; color: var(--if-text-secondary); }
header > .el-button { flex-shrink: 0; white-space: nowrap; padding: 0; height: auto; min-height: 24px; }
ol { list-style: none; padding: 0; margin: 12px 0 0; border-top: 1px solid var(--if-border); }
li { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 6px 16px; padding: 12px 0; border-bottom: 1px solid var(--if-border); font-size: 13px; }
li:last-child { padding-bottom: 0; border-bottom: 0; }
li div { display: flex; flex-wrap: wrap; gap: 6px 12px; min-width: 0; }
li strong { font-weight: 500; }
</style>
