<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getRelease } from '@/api/releases'
import { getVersion } from '@/api/versions'
import { usePermission } from '@/composables/usePermission'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import InfoGrid from '@/components/ui/InfoGrid.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import StatusTag from '@/components/StatusTag.vue'
import { formatLocalDateTime } from '@/utils/dates'
import type { ReleaseItem } from '@/types/domain'

const route = useRoute()
const { can } = usePermission()
const canViewVersion = computed(() => can('rd.version.view'))
const item = ref<ReleaseItem | null>(null)
const versionLabel = ref('')
const loading = ref(false)
const error = ref<'missing' | 'failed' | null>(null)
let releaseSequence = 0
let versionSequence = 0

async function load(): Promise<void> {
  const sequence = ++releaseSequence
  item.value = null
  error.value = null
  loading.value = true
  const id = Number(route.params.id)
  try {
    if (!Number.isSafeInteger(id) || id <= 0) {
      error.value = 'missing'
      return
    }
    const release = await getRelease(id)
    if (sequence === releaseSequence) item.value = release
  } catch (failure) {
    if (sequence === releaseSequence) {
      error.value = (failure as { response?: { status?: number } })?.response?.status === 404 ? 'missing' : 'failed'
    }
  } finally {
    if (sequence === releaseSequence) loading.value = false
  }
}

// Version metadata is optional and must never block the release record.
watch(() => [item.value?.version_id, canViewVersion.value] as const, async ([id, allowed]) => {
  const sequence = ++versionSequence
  versionLabel.value = ''
  if (id == null || !allowed) return
  try {
    const version = await getVersion(id)
    if (sequence === versionSequence) versionLabel.value = `${version.version_no} · ${version.name}`
  } catch {
    // Keep the version ID when metadata is unavailable or outside its scope.
  }
})

watch(() => route.params.id, load, { immediate: true })
onBeforeUnmount(() => { releaseSequence++; versionSequence++ })

const fields = computed(() => item.value ? [
  { label: '发布记录 ID', value: `#${item.value.id}` },
  { label: '所属版本', key: 'version' },
  { label: '发布时间', value: formatLocalDateTime(item.value.released_at) },
  { label: '发布结果', key: 'result' },
  { label: '创建人', value: item.value.created_by == null ? '系统' : `用户 #${item.value.created_by}` },
  { label: '创建时间', value: formatLocalDateTime(item.value.created_at) },
] : [])
</script>

<template>
  <section v-loading="loading" class="page release-detail" aria-label="发布记录详情">
    <PageHeader title="发布记录详情" :eyebrow="item ? `Release #${item.id}` : '发布'" description="查看实际发布结果与说明。">
      <template #actions><RouterLink class="back-link" to="/releases">返回发布记录</RouterLink></template>
    </PageHeader>
    <ErrorState v-if="error === 'missing'" title="发布记录不存在或不可访问" description="请返回发布记录列表。" />
    <ErrorState v-else-if="error === 'failed'" title="发布记录加载失败" description="请检查网络后重试。" retry-label="重新加载" @retry="load" />
    <template v-else-if="item">
      <SectionCard title="发布信息" description="发布记录为只读历史信息。">
        <InfoGrid :items="fields">
          <template #version>
            <RouterLink v-if="canViewVersion" class="version-link" :to="`/versions/${item.version_id}`">版本 #{{ item.version_id }}</RouterLink>
            <span v-else>版本 #{{ item.version_id }}</span>
            <div v-if="versionLabel" class="version-label">{{ versionLabel }}</div>
          </template>
          <template #result><StatusTag :status="item.result" label="成功" /></template>
        </InfoGrid>
      </SectionCard>
      <SectionCard title="发布说明"><p class="release-notes">{{ item.release_notes }}</p></SectionCard>
      <SectionCard title="回滚说明"><p class="release-notes">{{ item.rollback_notes ?? '—' }}</p></SectionCard>
    </template>
  </section>
</template>

<style scoped>
.back-link, .version-link { color: var(--if-brand-500); }
.version-label { margin-top: 4px; color: var(--if-text-2); overflow-wrap: anywhere; }
.release-notes { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7; }
</style>
