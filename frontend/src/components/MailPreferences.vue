<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { actionErrorMessage } from '@/utils/actionError'
import type { components } from '@/types/openapi.generated'
import SectionCard from './ui/SectionCard.vue'
type Preferences = components['schemas']['MailPreferencesOut']
type Delivery = components['schemas']['DeliveryOut']
const auth = useAuthStore()
const item = ref<Preferences | null>(null)
const mode = ref<Preferences['mode']>('TASKS'), email = ref(''), code = ref('')
const failed = ref(false), busy = ref(false), message = ref('')
const reverifying = ref(false)
const unbindDialog = ref(false), unbindRevision = ref<number | null>(null), unbindError = ref(''), unbindConflict = ref(false)
const showVerification = computed(() => !item.value?.verified || reverifying.value)
const deliveries = ref<Delivery[]>([]), page = ref(1), deliveriesOpen = ref(false), deliveryFailed = ref(false)
const admin = computed(() => auth.canViewApiDocs && auth.hasPermission('sys.user.edit'))
const identity = computed(() => `${auth.user?.id}:${auth.accessToken}:${auth.permissionCodes.join(',')}`)
let sequence = 0
async function load() {
  const request = ++sequence; failed.value = false; busy.value = false; item.value = null; deliveries.value = []; deliveriesOpen.value = false; reverifying.value = false; unbindDialog.value = false; unbindRevision.value = null; unbindError.value = ''; unbindConflict.value = false; message.value = ''
  if (!auth.user) return
  try { const { data } = await api.get<Preferences>('/me/mail-preferences'); if (request !== sequence) return; item.value = data; mode.value = data.mode; email.value = data.pending_email || data.email || ''; code.value = '' }
  catch { if (request === sequence) failed.value = true }
}
watch(identity, load, { immediate: true, flush: 'sync' })
onScopeDispose(() => { sequence++ })
async function mutate(path: string, data: object, method: 'post' | 'put' = 'post') {
  if (!item.value || busy.value) return
  const request = sequence
  busy.value = true; message.value = ''
  try {
    const response = await api[method]<Preferences>(path, { revision: item.value.revision, ...data })
    if (request !== sequence) return
    item.value = response.data; mode.value = response.data.mode; code.value = ''
    message.value = path.endsWith('confirm') ? '邮箱验证完成' : path.endsWith('email-verification') ? '验证邮件已排队，请查看邮箱；验证码 15 分钟内有效。' : '邮件偏好已保存'
    if (path.endsWith('confirm')) { reverifying.value = false; await auth.loadCurrentUser() }
  } catch { /* Shared API handler displays failure; leave inputs for manual retry. */ }
  finally { if (request === sequence) busy.value = false }
}
function openUnbind() {
  if (!item.value || busy.value) return
  unbindRevision.value = item.value.revision; unbindError.value = ''; unbindConflict.value = false; unbindDialog.value = true
}
async function unbind() {
  if (!item.value || busy.value || unbindRevision.value === null || unbindConflict.value) return
  const request = sequence
  busy.value = true; unbindError.value = ''; message.value = ''
  try {
    const { data } = await api.post<Preferences>('/me/email-unbind', { revision: unbindRevision.value }, { skipConflictAlert: true })
    if (request !== sequence) return
    item.value = data; mode.value = data.mode; email.value = ''; code.value = ''; reverifying.value = false
    unbindDialog.value = false; unbindRevision.value = null; message.value = '通知邮箱已取消绑定，站内通知仍可正常使用。'
    await auth.loadCurrentUser()
  } catch (error) {
    if (request !== sequence) return
    unbindError.value = actionErrorMessage(error)
    unbindConflict.value = (error as { response?: { status?: number } })?.response?.status === 409
  } finally { if (request === sequence) busy.value = false }
}
async function loadDeliveries() {
  const request = sequence; deliveryFailed.value = false; deliveriesOpen.value = true
  try { const { data } = await api.get<Delivery[]>('/admin/mail-deliveries', { params: { page: page.value } }); if (request === sequence && admin.value) deliveries.value = data }
  catch { if (request === sequence) deliveryFailed.value = true }
}
async function retry(row: Delivery) {
  busy.value = true
  try { await api.post(`/admin/mail-deliveries/${row.id}/retry`, { attempts: row.attempts }); await loadDeliveries() }
  catch { /* No automatic replay. */ }
  finally { busy.value = false }
}
const statusLabels: Record<string, string> = { PENDING: '待发送', SENDING: '发送中', RETRY: '等待重试', UNCERTAIN: '结果不确定，等待重试', FAILED: '发送失败', SKIPPED: '已跳过', SENT: '已发送' }
</script>
<template>
  <SectionCard id="mail-notifications" title="邮件通知" description="站内通知独立保留；邮件送达不代表业务确认。">
    <p v-if="failed">邮件设置加载失败 <el-button link @click="load">重试</el-button></p>
    <el-form v-else-if="item" label-position="top" @submit.prevent>
      <el-alert v-if="!item.smtp_enabled" title="邮件服务尚未启用，设置可先保存；启用后需验证邮箱才会发送。" type="info" :closable="false" />
      <el-form-item label="邮件偏好"><el-select v-model="mode"><el-option label="仅待办与上线（默认）" value="TASKS" /><el-option label="全部关键通知" value="ALL" /><el-option label="关闭邮件" value="OFF" /></el-select></el-form-item>
      <el-button :loading="busy" @click="mutate('/me/mail-preferences', { mode }, 'put')">保存偏好</el-button>
      <p>当前邮箱：{{ item.email || '未设置' }} · {{ item.verified ? '已验证' : '未验证，不发送进度邮件' }}</p>
      <p>默认仅发送待办与上线；验证后启用所选偏好，不补发历史进度。修改邮箱需重新验证。</p>
      <template v-if="showVerification">
        <el-form-item label="通知邮箱"><el-input v-model="email" type="email" autocomplete="email" maxlength="254" /></el-form-item>
        <p v-if="item.pending_email">待验证地址：{{ item.pending_email }}</p>
        <el-form-item label="六位验证码" for="mail-verification-code">
          <div class="verification-row">
            <el-input id="mail-verification-code" v-model="code" :disabled="!item.pending_email" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="请输入验证码" />
            <el-button :loading="busy" :disabled="!item.smtp_enabled || !email" @click="mutate('/me/email-verification', { email })">发送验证码</el-button>
          </div>
        </el-form-item>
        <el-button v-if="item.pending_email" :loading="busy" :disabled="!/^\d{6}$/.test(code)" @click="mutate('/me/email-verification/confirm', { code })">验证邮箱</el-button>
      </template>
      <div class="email-actions">
        <el-button v-if="!showVerification" :disabled="busy" @click="reverifying = true">重新验证</el-button>
        <el-button v-if="item.email || item.pending_email" type="danger" plain :disabled="busy" @click="openUnbind">取消绑定</el-button>
      </div>
      <p role="status">{{ message }}</p>
    </el-form>
    <el-dialog v-model="unbindDialog" title="取消绑定通知邮箱" width="min(460px, calc(100vw - 32px))" :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
      <p>取消后将清空当前通知邮箱和待验证地址，未完成的验证码也会失效。</p>
      <p>解绑后停止进度邮件，站内通知、邮件偏好及“我已知晓”记录保留。再次绑定邮箱需要重新验证。</p>
      <el-alert v-if="unbindError" :title="unbindError" type="error" :closable="false" />
      <template #footer>
        <div class="unbind-actions">
          <el-button :disabled="busy" @click="unbindDialog = false">暂不取消</el-button>
          <el-button v-if="unbindConflict" :disabled="busy" @click="load">刷新设置</el-button>
          <el-button v-else type="danger" :loading="busy" @click="unbind">确认取消绑定</el-button>
        </div>
      </template>
    </el-dialog>
    <template v-if="admin">
      <el-divider /><el-button @click="loadDeliveries">查看邮件投递记录</el-button>
      <div v-if="deliveriesOpen" class="mail-deliveries"><p v-if="deliveryFailed">投递记录加载失败，请重试。</p><p v-for="row in deliveries" :key="row.id">用户 #{{ row.user_id }} · {{ statusLabels[row.status] || row.status }} · 尝试 {{ row.attempts }} 次 · {{ row.last_error || '-' }} <el-button v-if="row.status === 'FAILED'" :loading="busy" @click="retry(row)">重新投递</el-button></p><el-button :disabled="page <= 1" @click="page--; loadDeliveries()">上一页</el-button><el-button :disabled="deliveries.length < 50" @click="page++; loadDeliveries()">下一页</el-button></div>
    </template>
  </SectionCard>
</template>
<style scoped>
.el-form { max-width: 560px; }.el-form-item { margin-top: 16px; }.el-select { width: 100%; }.mail-deliveries p { overflow-wrap: anywhere; border-bottom: 1px solid var(--if-border, #eee); padding: 10px 0; }
.verification-row { display: flex; align-items: stretch; gap: 8px; width: 100%; min-width: 0; }
.verification-row .el-input { flex: 1; min-width: 0; }
.verification-row .el-button { flex: none; margin: 0; white-space: nowrap; }
.email-actions, .unbind-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.email-actions .el-button, .unbind-actions .el-button { margin: 0; white-space: nowrap; }
.unbind-actions { justify-content: flex-end; }
@media (max-width: 767px) {
  .verification-row .el-input, .verification-row .el-button { min-height: 44px; }
  .email-actions .el-button, .unbind-actions .el-button { min-height: 44px; }
}
</style>
