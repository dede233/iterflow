<script setup lang="ts">
import { computed } from 'vue'
import { listMailDeliveryRecipients } from '@/api/mailDeliveryMonitor'
import { useScopedLookup } from '@/composables/useScopedLookup'
import { useScopedSearch } from '@/composables/useScopedSearch'
import { useAuthStore } from '@/stores/auth'

const PAGE_SIZE = 20
const model = defineModel<number | null>({ required: true })
const auth = useAuthStore()
const identity = computed(() => `${auth.user?.id ?? ''}:${auth.accessToken}`)
const selected = useScopedLookup(
  () => [model.value, auth.canViewMailDeliveries, identity.value] as const,
  async (id) => {
    const page = await listMailDeliveryRecipients({ selected_id: id, page_size: PAGE_SIZE })
    return page.items.find(item => item.user_id === id)
  },
)
const search = useScopedSearch(
  () => [auth.canViewMailDeliveries, identity.value] as const,
  async (keyword, page) => {
    const result = await listMailDeliveryRecipients({ keyword: Array.from(keyword).slice(0, 100).join('') || undefined, page, page_size: PAGE_SIZE })
    return {
      total: result.total,
      items: result.items.map(item => ({ id: item.user_id, title: item.display_name || item.username, code: item.username, status: '' })),
    }
  },
)
const options = computed(() => {
  const candidates = search.state.items.map(item => ({ id: item.id, name: item.title, username: item.code }))
  if (model.value !== null && !candidates.some(item => item.id === model.value)) {
    candidates.unshift({ id: model.value, name: selected.value?.display_name || selected.value?.username || '已选择收件人', username: selected.value?.username || '' })
  }
  return candidates
})

function update(value: number | undefined | null | ''): void {
  model.value = typeof value === 'number' ? value : null
}
</script>

<template>
  <el-select
    :model-value="model"
    aria-label="收件人"
    filterable
    clearable
    placeholder="搜索姓名或登录账号"
    no-data-text="没有匹配的邮件收件人，请检查姓名或登录账号"
    :filter-method="search.search"
    :loading="search.state.loading"
    @visible-change="$event ? search.open() : search.close()"
    @update:model-value="update"
  >
    <el-option
      v-for="option in options"
      :key="option.id"
      :value="option.id"
      :label="option.username && option.username !== option.name ? `${option.name}（${option.username}）` : option.name"
      class="recipient-option"
    >
      <span>{{ option.name }}</span><small v-if="option.username !== option.name">{{ option.username }}</small>
    </el-option>
    <template v-if="search.state.error || search.state.total > PAGE_SIZE || (search.state.keyword && !search.state.items.length && !search.state.loading && model !== null)" #footer>
      <div v-if="search.state.error" role="alert">收件人加载失败 <el-button link @click="search.retry">重试</el-button></div>
      <div v-else-if="search.state.total > PAGE_SIZE" class="recipient-pages">
        <el-button link :disabled="search.state.loading || search.state.page <= 1" @mousedown.prevent @click="search.paginate(search.state.page - 1)">上一页</el-button>
        <span>{{ search.state.page }} / {{ Math.ceil(search.state.total / PAGE_SIZE) }}</span>
        <el-button link :disabled="search.state.loading || search.state.page * PAGE_SIZE >= search.state.total" @mousedown.prevent @click="search.paginate(search.state.page + 1)">下一页</el-button>
      </div>
      <p v-else class="recipient-empty" role="status">没有匹配的邮件收件人，请检查姓名或登录账号</p>
    </template>
  </el-select>
</template>

<style scoped>
.recipient-option { display: flex; gap: 12px; align-items: center; }
.recipient-option span, .recipient-option small { overflow: hidden; text-overflow: ellipsis; }
.recipient-option small, .recipient-empty { color: var(--if-text-2); font-size: 12px; }
.recipient-empty { margin: 0; }
.recipient-pages { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 12px; }
.recipient-pages :deep(.el-button + .el-button) { margin-left: 0; }
@media (max-width: 767px) {
  .recipient-option, .recipient-pages :deep(.el-button), :deep(.el-select__wrapper) { min-height: 44px; }
}
</style>
