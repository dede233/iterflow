<script setup lang="ts">
import { computed, onMounted, onScopeDispose, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import type { components } from '@/types/openapi.generated'

type Preferences = components['schemas']['MailPreferencesOut']
const emit = defineEmits<{ visibility: [visible: boolean] }>()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const item = ref<Preferences | null>(null)
const dismissed = ref(false), busy = ref(false), error = ref('')
const identity = computed(() => `${auth.user?.id ?? ''}:${auth.accessToken}`)
const eligiblePage = computed(() => route.path !== '/profile' && !auth.mustChangePassword)
const visible = computed(() => Boolean(auth.user && eligiblePage.value && !dismissed.value && item.value?.smtp_enabled
  && item.value.mode !== 'OFF' && !item.value.verified && item.value.notice_acknowledged === false))
watch(visible, value => emit('visibility', value), { immediate: true })
const hasEmail = computed(() => Boolean(item.value?.pending_email || item.value?.email))
let sequence = 0

async function load() {
  const request = ++sequence
  item.value = null; busy.value = false; error.value = ''
  if (!auth.user || !eligiblePage.value || dismissed.value) return
  try {
    const { data } = await api.get<Preferences>('/me/mail-preferences')
    if (request === sequence) item.value = data
  } catch { /* A background notice must not block normal use when settings cannot be loaded. */ }
}
onMounted(() => {
  watch(identity, () => { dismissed.value = false; void load() }, { immediate: true, flush: 'sync' })
  watch(eligiblePage, () => { void load() }, { flush: 'sync' })
})
onScopeDispose(() => { sequence++ })

async function acknowledge() {
  if (!item.value || busy.value) return
  const request = sequence
  busy.value = true; error.value = ''
  try {
    const { data } = await api.post<Preferences>('/me/mail-notice/acknowledge', { revision: item.value.revision }, { skipConflictAlert: true })
    if (request !== sequence) return
    item.value = data
    dismissed.value = true
  } catch (failure: any) {
    if (request !== sequence) return
    if (failure.response?.status === 409) {
      const refreshed = sequence + 1
      await load()
      if (sequence === refreshed && visible.value) error.value = '邮件设置已更新，请重新点击“我已知晓”。'
    } else error.value = '未能保存知晓状态，请重试，或暂时关闭提示。'
  } finally { if (request === sequence) busy.value = false }
}
function close() { if (!busy.value) dismissed.value = true }
function setupEmail() {
  dismissed.value = true
  void router.push('/profile#mail-notifications')
}
</script>

<template>
  <el-dialog :model-value="visible" title="邮件通知已上线" width="min(460px, calc(100vw - 32px))"
    :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy"
    @update:model-value="(value: boolean) => { if (!value) close() }">
    <p>{{ hasEmail ? '你的通知邮箱尚未完成验证。' : '你还没有绑定通知邮箱。' }}完成邮箱验证后，可接收待办和上线等进度通知。</p>
    <p class="notice-detail">站内通知仍可正常使用；邮件送达不代表需求确认或验收。你可以随时在个人中心调整邮件偏好。</p>
    <p class="notice-detail">点击“我已知晓”后，此账号在所有设备上都不再弹出此提示。</p>
    <p v-if="error" role="alert" class="notice-error">{{ error }}</p>
    <template #footer>
      <div class="notice-actions">
        <el-button :loading="busy" @click="acknowledge">我已知晓</el-button>
        <el-button type="primary" :disabled="busy" @click="setupEmail">{{ hasEmail ? '去验证邮箱' : '去绑定邮箱' }}</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
p { line-height: 1.7; margin: 0 0 12px; }
.notice-detail { color: var(--if-text-3); font-size: 13px; }
.notice-error { color: var(--el-color-danger); }
.notice-actions { display: flex; justify-content: flex-end; gap: 12px; }
.notice-actions .el-button { margin: 0; white-space: nowrap; }
@media (max-width: 767px) { .notice-actions .el-button { flex: 1; min-height: 44px; } }
</style>
