<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { isAxiosError } from 'axios'
import { useRoute, useRouter } from 'vue-router'
import { getAdProduction, type AdProduction } from '@/api/adProductions'
import ErrorState from '@/components/ui/ErrorState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { AD_PRODUCTION_LABELS, type AdProductionKind } from '@/constants/adProduction'
import AdProductionDetail from './AdProductionDetail.vue'

const props = defineProps<{ kind: AdProductionKind }>()
const route = useRoute()
const router = useRouter()
const title = computed(() => `${AD_PRODUCTION_LABELS[props.kind].name}详情`)
const state = ref<'loading' | 'ready' | 'unavailable' | 'error'>('loading')
const record = shallowRef<AdProduction | null>(null)
let currentRequest: AbortController | undefined

async function load(): Promise<void> {
  currentRequest?.abort()
  record.value = null
  const rawId = route.params.id
  const id = typeof rawId === 'string' && /^\d+$/.test(rawId) ? Number(rawId) : NaN
  if (!Number.isSafeInteger(id) || id < 1) {
    state.value = 'unavailable'
    return
  }
  const request = new AbortController()
  currentRequest = request
  state.value = 'loading'
  try {
    const result = await getAdProduction(id, request.signal)
    if (request.signal.aborted) return
    if (result.id !== id || (result.kind ?? 'MATERIAL') !== props.kind) {
      state.value = 'unavailable'
      return
    }
    record.value = result
    state.value = 'ready'
  } catch (error) {
    if (request.signal.aborted) return
    const status = isAxiosError(error) ? error.response?.status : undefined
    state.value = status === 403 || status === 404 ? 'unavailable' : 'error'
  }
}

watch(() => [props.kind, route.params.id], load, { immediate: true })
onBeforeUnmount(() => currentRequest?.abort())
</script>

<template>
  <section class="page">
    <PageHeader :title="title">
      <template #actions>
        <el-button @click="router.push({ name: 'notifications' })">返回通知中心</el-button>
      </template>
    </PageHeader>
    <div class="notification-detail" data-testid="ad-production-notification-detail">
      <p v-if="state === 'loading'" role="status">正在加载记录…</p>
      <ErrorState v-else-if="state === 'unavailable'" title="无法查看此记录" description="记录可能已不可用，或你的查看权限已变更。" />
      <ErrorState v-else-if="state === 'error'" title="记录加载失败" retry-label="重新加载" @retry="load" />
      <AdProductionDetail v-else-if="record" :record="record" />
    </div>
  </section>
</template>

<style scoped>
.notification-detail { max-width: 980px; }
.notification-detail > p { color: var(--if-text-secondary); }
</style>
