<script setup lang="ts">
import { computed, onScopeDispose, ref, useId, watch } from 'vue'
import { ElMessage, type ButtonInstance } from 'element-plus'
import { withdrawAdProduction, type AdProduction } from '@/api/adProductions'
import { deleteEntity, type EntityDeleteKind } from '@/api/entityActions'
import { useAuthStore } from '@/stores/auth'
import { actionErrorMessage } from '@/utils/actionError'

const props = withDefaults(defineProps<{
  kind: EntityDeleteKind
  id: number
  revision: number
  recordNumber?: string
  title: string
  action?: 'delete' | 'withdraw'
}>(), { action: 'delete' })
const emit = defineEmits<{ deleted: []; withdrawn: [record: AdProduction]; refresh: [] }>()
const auth = useAuthStore()
const trigger = ref<ButtonInstance>()
const open = ref(false)
const busy = ref(false)
const reason = ref('')
const attempted = ref(false)
const error = ref('')
const reasonId = useId()
const withdrawing = computed(() => props.action === 'withdraw')
const actionLabel = computed(() => withdrawing.value ? '撤回' : '删除')
const trimmedReason = computed(() => reason.value.trim())
const validReason = computed(() => [...trimmedReason.value].length >= 2)
let sequence = 0
const identity = computed(() => `${auth.user?.id}:${auth.accessToken}:${auth.permissionCodes.join(',')}`)
watch(() => [props.kind, props.id, props.revision, props.action, identity.value], () => {
  sequence++
  open.value = false
  busy.value = false
})
onScopeDispose(() => { sequence++ })

function begin(): void {
  reason.value = ''
  attempted.value = false
  error.value = ''
  open.value = true
}

async function submit(): Promise<void> {
  if (busy.value) return
  attempted.value = true
  error.value = ''
  if (!validReason.value) return
  const payload = { revision: props.revision, reason: trimmedReason.value }
  const request = ++sequence
  busy.value = true
  try {
    let updated: AdProduction | undefined
    if (withdrawing.value) updated = await withdrawAdProduction(props.id, payload)
    else await deleteEntity(props.kind, props.id, payload)
    if (request !== sequence) return
    open.value = false
    ElMessage.success(`已${actionLabel.value}`)
    if (updated) emit('withdrawn', updated)
    else emit('deleted')
  } catch (failure) {
    if (request === sequence) error.value = actionErrorMessage(failure)
  } finally {
    if (request === sequence) busy.value = false
  }
}
</script>

<template>
  <el-dropdown trigger="click" @command="begin">
    <el-button ref="trigger" class="lifecycle-trigger">更多</el-button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item :command="action">{{ actionLabel }}</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
  <el-dialog v-model="open" :title="`确认${actionLabel}`" width="min(480px, calc(100vw - 24px))" append-to-body :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" @closed="trigger?.ref?.focus()">
    <p class="lifecycle-id">编号 {{ recordNumber || id }}</p>
    <p class="lifecycle-confirmation" v-if="withdrawing">撤回「{{ title }}」后，当前处理将结束，记录将保留。</p>
    <p class="lifecycle-confirmation" v-else>删除「{{ title }}」后，它将从列表中移除。历史记录将保留。</p>
    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item :label="`${actionLabel}原因`" :for="reasonId" required>
        <el-input :id="reasonId" v-model="reason" type="textarea" :rows="3" :maxlength="500" :disabled="busy" />
      </el-form-item>
      <p v-if="attempted && !validReason" class="lifecycle-error" role="alert">请填写{{ actionLabel }}原因（至少 2 个字符）</p>
      <p v-else-if="error" class="lifecycle-error" role="alert">{{ error }} <el-button link :disabled="busy" @click="open = false; emit('refresh')">刷新详情</el-button></p>
      <div class="lifecycle-buttons">
        <el-button :disabled="busy" @click="open = false">取消</el-button>
        <el-button type="danger" native-type="submit" :loading="busy">确认{{ actionLabel }}</el-button>
      </div>
    </el-form>
  </el-dialog>
</template>

<style scoped>
.lifecycle-id { color: var(--el-text-color-secondary); overflow-wrap: anywhere; }
.lifecycle-confirmation { overflow-wrap: anywhere; }
.lifecycle-error { color: var(--if-danger-fg); }
.lifecycle-buttons { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: var(--if-space-2); }
.lifecycle-buttons :deep(.el-button + .el-button) { margin-left: 0; }
@media (max-width: 767px) {
  .lifecycle-trigger, .lifecycle-buttons :deep(.el-button) { min-height: 44px; }
}
</style>
