<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useResponsive } from '@/composables/useResponsive'
import { usePermission } from '@/composables/usePermission'
import { detailTarget } from '@/utils/listQuery'

// Lazy loading keeps the standalone detail routes and this shared host cycle safe.
const ReleaseDetail = defineAsyncComponent(() => import('@/views/release/ReleaseDetailView.vue'))
const VersionDetail = defineAsyncComponent(() => import('@/views/version/VersionDetailView.vue'))
type Entry = { kind: 'release' | 'version'; id: number }
const props = defineProps<{ modelValue: boolean; kind: Entry['kind']; id: number | null; returnTo: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; updated: [] }>()
const router = useRouter()
const { isMobile } = useResponsive()
const { can } = usePermission()
const history = ref<Entry[]>([])
const current = computed(() => history.value.at(-1))
const title = computed(() => current.value?.kind === 'version' ? '版本详情' : '发布记录详情')
const open = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const allowed = (entry: Entry) => Number.isSafeInteger(entry.id) && entry.id > 0 && can(entry.kind === 'version' ? 'rd.version.view' : 'rd.release.view')
const visible = computed(() => !!current.value && allowed(current.value))

watch(() => [props.modelValue, props.kind, props.id] as const, ([opened, kind, id]) => {
  history.value = opened && id != null ? [{ kind, id }] : []
}, { immediate: true })

function navigate(kind: Entry['kind'], id: number): void {
  const entry = { kind, id }
  if (!allowed(entry)) return
  const existing = history.value.findIndex(item => item.kind === kind && item.id === id)
  if (existing >= 0) history.value = history.value.slice(0, existing + 1)
  else history.value.push(entry)
}

async function expand(): Promise<void> {
  if (!current.value || !visible.value) return
  const { kind, id } = current.value
  await router.push(detailTarget(`/${kind === 'version' ? 'versions' : 'releases'}/${id}`, props.returnTo))
  open.value = false
}
</script>

<template>
  <el-drawer v-model="open" :title="title" direction="rtl" :size="isMobile ? '100%' : 'min(960px, 94vw)'" destroy-on-close class="detail-drawer">
    <template #header>
      <div class="detail-header">
        <span class="detail-title">{{ title }}</span>
        <div class="detail-actions">
          <el-button v-if="history.length > 1" size="small" @click="history.pop()">返回上个详情</el-button>
          <el-button v-if="visible" size="small" @click="expand">新标签/全屏直达</el-button>
        </div>
      </div>
    </template>
    <component
      :is="current?.kind === 'version' ? VersionDetail : ReleaseDetail"
      v-if="open && current && visible"
      :key="`${current.kind}:${current.id}`"
      embedded
      :embedded-id="current.id"
      :return-to="returnTo"
      @close="open = false"
      @updated="emit('updated')"
      @open-version="(id: number) => navigate('version', id)"
      @open-release="(id: number) => navigate('release', id)"
    />
  </el-drawer>
</template>

<style scoped>
.detail-header { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; width: 100%; min-width: 0; }
.detail-title { font-size: 16px; font-weight: 600; }
.detail-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-left: auto; }
.detail-actions :deep(.el-button + .el-button) { margin-left: 0; }
</style>
