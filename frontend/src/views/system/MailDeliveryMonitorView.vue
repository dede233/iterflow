<script setup lang="ts">
import { isAxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import { computed, onScopeDispose, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  getMailDeliveryDetail,
  listMailDeliveryMonitor,
  resendMailDelivery,
  retryMailDelivery,
  type MailDeliveryDetail,
} from '@/api/mailDeliveryMonitor'
import StatusTag from '@/components/StatusTag.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import ListFilterPanel from '@/components/ui/ListFilterPanel.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import { useListQuery } from '@/composables/useListQuery'
import { useResponsive } from '@/composables/useResponsive'
import {
  MAIL_DELIVERY_KINDS,
  MAIL_DELIVERY_KIND_LABELS,
  MAIL_DELIVERY_STATUSES,
  mailDeliveryReason,
  mailDeliveryStatus,
  type MailDeliveryItem,
  type MailDeliveryKind,
  type MailDeliveryStatus,
} from '@/constants/mailDelivery'
import { useAuthStore } from '@/stores/auth'
import { formatLocalDateTime } from '@/utils/dates'
import MailDeliveryRecipientSelect from './MailDeliveryRecipientSelect.vue'

type DetailState =
  | { status: 'loading' }
  | { status: 'ready'; delivery: MailDeliveryDetail }
  | { status: 'failed'; title: string; retry?: true }

const PAGE_SIZE = 20
const auth = useAuthStore()
const router = useRouter()
const { isDesktop, isMobile } = useResponsive()
const rows = ref<MailDeliveryItem[]>([])
const loading = ref(true)
const failure = ref<'forbidden' | 'load' | null>(null)
const kind = ref<MailDeliveryKind | ''>('')
const status = ref<MailDeliveryStatus | ''>('')
const recipientId = ref<number | null>(null)
const filterDrawer = ref(false)
const appliedFilters = ref(0)
const currentPage = ref(1)
const total = ref(0)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const canResend = ref(false)
const canRetry = computed(() => !canResend.value && auth.canViewApiDocs && auth.hasPermission('sys.user.edit'))
const submitting = ref(new Set<string>())
const resendCandidate = ref<MailDeliveryItem | null>(null)
const resendSubmitting = computed(() => resendCandidate.value !== null && submitting.value.has(resendCandidate.value.id))
const detailId = ref<string | null>(null)
const detail = ref<DetailState>({ status: 'loading' })
let detailRequest: AbortController | undefined
let sequence = 0
let disposed = false
onScopeDispose(() => {
  disposed = true
  detailRequest?.abort()
})

watch(() => auth.canViewMailDeliveries, (allowed) => {
  if (!allowed) {
    sequence++
    rows.value = []
    closeDetail()
    void router.replace({ name: 'forbidden' })
  }
})

function closeDetail(): void {
  detailRequest?.abort()
  detailRequest = undefined
  detailId.value = null
}

function clearClosedDetail(): void {
  if (detailId.value === null) detail.value = { status: 'loading' }
}

async function openDetail(id: string): Promise<void> {
  if (!auth.canViewMailDeliveries) return
  detailRequest?.abort()
  const request = new AbortController()
  detailRequest = request
  detailId.value = id
  detail.value = { status: 'loading' }
  try {
    const delivery = await getMailDeliveryDetail(id, request.signal)
    if (!request.signal.aborted) detail.value = { status: 'ready', delivery }
  } catch (error) {
    if (request.signal.aborted) return
    const status = isAxiosError(error) ? error.response?.status : undefined
    if (status === 403) detail.value = { status: 'failed', title: '当前账号无权查看投递详情' }
    else if (status === 404) detail.value = { status: 'failed', title: '投递记录已无法查看' }
    else detail.value = { status: 'failed', title: '投递详情加载失败', retry: true }
  }
}

function reloadDetail(): void {
  if (detailId.value) void openDetail(detailId.value)
}

async function load(): Promise<void> {
  if (!auth.canViewMailDeliveries) return
  const request = ++sequence
  const applied = queryState.applied()
  const page = Number(applied.page ?? 1)
  loading.value = true
  failure.value = null
  rows.value = []
  try {
    const result = await listMailDeliveryMonitor({
      page,
      page_size: PAGE_SIZE,
      kind: applied.kind as MailDeliveryKind | undefined,
      status: applied.status as MailDeliveryStatus | undefined,
      user_id: applied.user_id ? Number(applied.user_id) : undefined,
    })
    if (request !== sequence) return
    canResend.value = result.can_resend_mail_deliveries === true
    total.value = result.total
    if (page > pageCount.value) {
      void queryState.paginate(pageCount.value)
      return
    }
    rows.value = result.items
  } catch (error) {
    if (request !== sequence) return
    failure.value = isAxiosError(error) && error.response?.status === 403 ? 'forbidden' : 'load'
  } finally {
    if (request === sequence) loading.value = false
  }
}

async function submitDelivery(id: string, action: () => Promise<void>): Promise<void> {
  if (!auth.canViewMailDeliveries || submitting.value.has(id)) return
  submitting.value.add(id)
  try {
    await action()
    if (!disposed && auth.canViewMailDeliveries) ElMessage.success('邮件已重新排队')
  } catch (error) {
    if (!disposed && auth.canViewMailDeliveries) {
      const statusCode = isAxiosError(error) ? error.response?.status : undefined
      if (statusCode === 409) ElMessage.warning('投递记录已变化，请查看最新状态。')
      else if (statusCode !== 403) ElMessage.error('未能确认重新排队，请查看最新状态。')
    }
  } finally {
    if (!disposed && auth.canViewMailDeliveries) await load()
    submitting.value.delete(id)
  }
}

function retry(row: MailDeliveryItem): void {
  if (canRetry.value && row.status === 'FAILED') {
    void submitDelivery(row.id, () => retryMailDelivery(row.id, { attempts: row.attempts }))
  }
}

async function confirmResend(): Promise<void> {
  const row = resendCandidate.value
  if (!row?.resend_token || !canResend.value || resendSubmitting.value) return
  const resendToken = row.resend_token
  await submitDelivery(row.id, () => resendMailDelivery(row.id, { resend_token: resendToken }))
  resendCandidate.value = null
}

const queryState = useListQuery({
  path: '/admin/mail-delivery-monitor',
  readDraft: () => ({ kind: kind.value, status: status.value, user_id: recipientId.value }),
  restore: (query) => {
    kind.value = (query.kind ?? '') as MailDeliveryKind | ''
    status.value = (query.status ?? '') as MailDeliveryStatus | ''
    recipientId.value = query.user_id ? Number(query.user_id) : null
    appliedFilters.value = Number(Boolean(query.kind)) + Number(Boolean(query.status)) + Number(Boolean(query.user_id))
    currentPage.value = Number(query.page ?? 1)
  },
  load,
  invalidate: () => { sequence++ },
})

function applyFilters(): void {
  filterDrawer.value = false
  void queryState.apply()
}

function resetFilters(): void {
  filterDrawer.value = false
  void queryState.reset()
}
</script>

<template>
  <section v-if="auth.canViewMailDeliveries" class="page">
    <PageHeader
      title="邮件记录"
      description="「已发送」表示 SMTP 服务器已接受邮件。收件箱送达情况与阅读状态未知。"
    >
      <template v-if="failure !== 'forbidden'" #actions>
        <el-button :loading="loading" @click="load">刷新记录</el-button>
        <el-button v-if="isMobile" @click="filterDrawer = true">筛选{{ appliedFilters ? ` (${appliedFilters})` : '' }}</el-button>
      </template>
    </PageHeader>

    <ErrorState v-if="failure === 'forbidden'" title="邮件记录不可访问" description="当前账号无权查看邮件记录。" />
    <template v-else>
      <ListFilterPanel v-model="filterDrawer" :mobile="isMobile" class="mail-record-filters" title="筛选邮件记录" @search="applyFilters" @reset="resetFilters">
        <el-form-item label="邮件类型">
          <el-select v-model="kind" class="filter-select" aria-label="邮件类型" placeholder="全部类型">
            <el-option label="全部类型" value="" />
            <el-option v-for="option in MAIL_DELIVERY_KINDS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="投递状态">
          <el-select v-model="status" class="filter-select" aria-label="投递状态" placeholder="全部状态">
            <el-option label="全部状态" value="" />
            <el-option v-for="option in MAIL_DELIVERY_STATUSES" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="收件人"><MailDeliveryRecipientSelect v-model="recipientId" /></el-form-item>
      </ListFilterPanel>

      <SectionCard title="投递记录" :description="loading || failure ? undefined : `共 ${total} 条记录`" :padded="false">
        <div :aria-busy="loading">
          <p v-if="loading" class="loading-state" role="status">正在加载投递记录…</p>
          <ErrorState v-else-if="failure === 'load'" class="list-error" title="投递记录加载失败" retry-label="重新加载" @retry="load" />
          <EmptyState v-else-if="!rows.length" :description="appliedFilters ? '当前条件下暂无投递记录' : '暂无投递记录'" compact />

          <el-table v-else-if="isDesktop" :data="rows" row-key="id" class="delivery-table">
            <el-table-column label="邮件类型" min-width="130">
              <template #default="{ row }">
                <strong>{{ MAIL_DELIVERY_KIND_LABELS[row.kind as MailDeliveryItem['kind']] }}</strong>
              </template>
            </el-table-column>
            <el-table-column label="收件人" min-width="136">
              <template #default="{ row }">
                <span class="account-name">{{ row.display_name || row.username }}</span>
                <span v-if="row.display_name && row.display_name !== row.username" class="secondary account-name">{{ row.username }}</span>
              </template>
            </el-table-column>
            <el-table-column label="投递状态" min-width="110">
              <template #default="{ row }">
                <StatusTag :status="row.status" v-bind="mailDeliveryStatus(row.status)" />
                <span class="secondary">尝试 {{ row.attempts }} 次</span>
              </template>
            </el-table-column>
            <el-table-column label="最近原因" min-width="128">
              <template #default="{ row }">{{ mailDeliveryReason(row.error_code) }}</template>
            </el-table-column>
            <el-table-column label="创建时间" min-width="144">
              <template #default="{ row }">{{ formatLocalDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="下次尝试" min-width="144">
              <template #default="{ row }">{{ row.next_attempt_at ? formatLocalDateTime(row.next_attempt_at) : '—' }}</template>
            </el-table-column>
            <el-table-column label="操作" :width="canResend || canRetry ? 164 : 96" fixed="right">
              <template #default="{ row }">
                <div class="delivery-actions">
                  <el-button link type="primary" aria-haspopup="dialog" @click="openDetail(row.id)">查看详情</el-button>
                  <el-button v-if="canResend" link type="primary" :disabled="!row.resend_token" :loading="submitting.has(row.id)" :aria-describedby="!row.resend_token ? `resend-block-${row.id}` : undefined" @click="resendCandidate = row">重发邮件</el-button>
                  <el-button v-else-if="canRetry && row.status === 'FAILED'" link type="primary" :loading="submitting.has(row.id)" @click="retry(row)">重新投递</el-button>
                </div>
                <span v-if="canResend && !row.resend_token" :id="`resend-block-${row.id}`" class="resend-block-reason">{{ row.resend_block_reason || '当前记录暂不能重发。' }}</span>
              </template>
            </el-table-column>
          </el-table>

          <ul v-else class="delivery-cards" aria-label="投递记录">
            <li v-for="item in rows" :key="item.id" class="delivery-card">
              <div class="card-header">
                <strong>{{ MAIL_DELIVERY_KIND_LABELS[item.kind] }}</strong>
                <StatusTag :status="item.status" v-bind="mailDeliveryStatus(item.status)" />
              </div>
              <dl class="card-fields">
                <dt>收件人</dt><dd><span>{{ item.display_name || item.username }}</span><span v-if="item.display_name && item.display_name !== item.username" class="secondary">{{ item.username }}</span></dd>
                <dt>尝试次数</dt><dd>{{ item.attempts }}</dd>
                <dt>最近原因</dt><dd>{{ mailDeliveryReason(item.error_code) }}</dd>
                <dt>创建时间</dt><dd>{{ formatLocalDateTime(item.created_at) }}</dd>
                <dt>下次尝试</dt><dd>{{ item.next_attempt_at ? formatLocalDateTime(item.next_attempt_at) : '—' }}</dd>
              </dl>
              <div class="delivery-actions card-actions">
                <el-button aria-haspopup="dialog" @click="openDetail(item.id)">查看详情</el-button>
                <el-button v-if="canResend" type="primary" plain :disabled="!item.resend_token" :loading="submitting.has(item.id)" :aria-describedby="!item.resend_token ? `resend-block-${item.id}` : undefined" @click="resendCandidate = item">重发邮件</el-button>
                <el-button v-else-if="canRetry && item.status === 'FAILED'" type="primary" plain :loading="submitting.has(item.id)" @click="retry(item)">重新投递</el-button>
              </div>
              <span v-if="canResend && !item.resend_token" :id="`resend-block-${item.id}`" class="resend-block-reason">{{ item.resend_block_reason || '当前记录暂不能重发。' }}</span>
            </li>
          </ul>
        </div>
      </SectionCard>

      <nav v-if="!failure && pageCount > 1" class="pager" aria-label="投递记录分页" :aria-busy="loading">
        <el-button :disabled="loading || currentPage <= 1" @click="queryState.paginate(currentPage - 1)">上一页</el-button>
        <span role="status">第 {{ currentPage }} / {{ pageCount }} 页</span>
        <el-button :disabled="loading || currentPage >= pageCount" @click="queryState.paginate(currentPage + 1)">下一页</el-button>
      </nav>
    </template>

    <el-dialog
      :model-value="detailId !== null"
      title="投递详情"
      width="min(520px, calc(100vw - 32px))"
      append-to-body
      destroy-on-close
      @close="closeDetail"
      @closed="clearClosedDetail"
    >
      <p v-if="detail.status === 'loading'" class="loading-state" role="status">正在加载投递详情…</p>
      <ErrorState
        v-else-if="detail.status === 'failed'"
        class="detail-error"
        :title="detail.title"
        :retry-label="detail.retry ? '重新加载' : undefined"
        @retry="reloadDetail"
      />
      <dl v-else class="card-fields detail-fields">
        <dt>收件人</dt>
        <dd>
          <span>{{ detail.delivery.display_name || detail.delivery.username }}</span>
          <span v-if="detail.delivery.display_name && detail.delivery.display_name !== detail.delivery.username" class="secondary">{{ detail.delivery.username }}</span>
        </dd>
        <dt>投递时收件地址</dt><dd>{{ detail.delivery.masked_email ?? '暂无记录' }}</dd>
        <dt>邮件类型</dt><dd>{{ MAIL_DELIVERY_KIND_LABELS[detail.delivery.kind] }}</dd>
        <dt>邮件事件</dt><dd>{{ detail.delivery.event_label }}</dd>
        <dt>事件时间</dt><dd><time :datetime="detail.delivery.event_created_at">{{ formatLocalDateTime(detail.delivery.event_created_at) }}</time></dd>
        <dt>投递状态</dt>
        <dd>
          <StatusTag :status="detail.delivery.status" v-bind="mailDeliveryStatus(detail.delivery.status)" />
          <span v-if="detail.delivery.status === 'SENT'" class="detail-status-note">SMTP 服务器已接受邮件，收件箱送达及阅读状态未知。</span>
        </dd>
        <dt>尝试次数</dt><dd>{{ detail.delivery.attempts }}</dd>
        <dt>最近原因</dt><dd>{{ mailDeliveryReason(detail.delivery.error_code) }}</dd>
        <dt>投递创建时间</dt><dd><time :datetime="detail.delivery.created_at">{{ formatLocalDateTime(detail.delivery.created_at) }}</time></dd>
        <dt>下次尝试</dt>
        <dd><time v-if="detail.delivery.next_attempt_at" :datetime="detail.delivery.next_attempt_at">{{ formatLocalDateTime(detail.delivery.next_attempt_at) }}</time><template v-else>—</template></dd>
      </dl>
      <template #footer>
        <el-button @click="closeDetail">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      :model-value="resendCandidate !== null"
      title="确认重发邮件"
      width="min(460px, calc(100vw - 32px))"
      append-to-body
      :close-on-click-modal="false"
      :close-on-press-escape="!resendSubmitting"
      :show-close="!resendSubmitting"
      @close="resendCandidate = null"
    >
      <template v-if="resendCandidate">
        <p class="resend-prompt">确认将邮件重新排队发送？</p>
        <dl class="card-fields">
          <dt>收件人</dt>
          <dd>{{ resendCandidate.display_name && resendCandidate.display_name !== resendCandidate.username ? `${resendCandidate.display_name}（${resendCandidate.username}）` : resendCandidate.username }}</dd>
          <dt>邮件类型</dt>
          <dd>{{ MAIL_DELIVERY_KIND_LABELS[resendCandidate.kind] }}</dd>
        </dl>
      </template>
      <template #footer>
        <el-button class="resend-dialog-action" :disabled="resendSubmitting" @click="resendCandidate = null">取消</el-button>
        <el-button class="resend-dialog-action" type="primary" :loading="resendSubmitting" @click="confirmResend">确认重发</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.loading-state { margin: 0; padding: 36px var(--if-space-4); color: var(--if-text-2); text-align: center; }
.list-error { border: 0; }
.secondary { display: block; color: var(--if-text-3); font-size: 12px; }
.account-name { overflow-wrap: anywhere; }
.delivery-cards { display: grid; gap: 10px; margin: 0; padding: var(--if-space-4); list-style: none; }
.delivery-card { min-width: 0; padding: 14px; border: 1px solid var(--if-border); border-radius: var(--if-radius); }
.card-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.card-fields { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 6px 12px; margin: 12px 0 0; font-size: 13px; }
.card-fields dt { color: var(--if-text-3); }
.card-fields dd { margin: 0; min-width: 0; overflow-wrap: anywhere; }
.delivery-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 8px; }
.delivery-actions .el-button { margin: 0; }
.card-actions { margin-top: 12px; }
.resend-block-reason { display: block; color: var(--if-text-2); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.delivery-actions + .resend-block-reason { margin-top: 4px; }
.detail-fields { margin: 0; gap: 10px 16px; font-size: 14px; }
.detail-fields dt, .detail-status-note { color: var(--if-text-secondary); }
.detail-status-note { display: block; margin-top: 4px; font-size: 13px; }
.detail-error { border: 0; }
.resend-prompt { margin: 0; }
.pager { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 12px; margin-top: var(--if-space-4); color: var(--if-text-2); font-size: 13px; }
.pager .el-button { margin: 0; }
@media (max-width: 767px) {
  .card-actions .el-button, .resend-dialog-action, .pager .el-button, .list-error :deep(.error-state__btn), .detail-error :deep(.error-state__btn) { min-height: 44px; }
  .filter-select :deep(.el-select__wrapper), :global(.mail-record-filters .el-drawer__footer .el-button) { min-height: 44px; }
  .pager { justify-content: center; }
}
</style>
