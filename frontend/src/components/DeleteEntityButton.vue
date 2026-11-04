<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { deleteEntity, type ActionKind } from '@/api/entityActions'
import { useAuthStore } from '@/stores/auth'
import { actionErrorMessage } from '@/utils/actionError'
const props = defineProps<{ kind: ActionKind; id: number; revision: number; title: string }>()
const emit = defineEmits<{ deleted: []; refresh: [] }>()
const auth = useAuthStore()
const open = ref(false)
const busy = ref(false)
const reason = ref('')
const error = ref('')
let sequence = 0
const identity = computed(() => `${auth.user?.id}:${auth.accessToken}:${auth.permissionCodes.join(',')}`)
watch(() => [props.id, props.revision, identity.value], () => { sequence++; open.value = false; busy.value = false })
onScopeDispose(() => { sequence++ })
function begin() { reason.value = ''; error.value = ''; open.value = true }
async function submit() {
  if (busy.value) return
  if (reason.value.trim().length < 2) { error.value = '请填写删除原因（至少 2 个字符）'; return }
  const request = ++sequence
  busy.value = true; error.value = ''
  try {
    await deleteEntity(props.kind, props.id, { revision: props.revision, reason: reason.value.trim() })
    if (request !== sequence) return
    open.value = false; emit('deleted')
  } catch (e) { if (request === sequence) error.value = actionErrorMessage(e) }
  finally { if (request === sequence) busy.value = false }
}
</script>
<template>
  <el-button type="danger" plain @click="begin">删除</el-button>
  <el-dialog v-model="open" title="确认删除" width="min(480px, calc(100vw - 24px))" append-to-body :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy">
    <p>删除「{{ title }}」后，它将从列表中移除。历史记录将保留。</p>
    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="删除原因" required><el-input v-model="reason" type="textarea" :maxlength="500" :disabled="busy" /></el-form-item>
      <p v-if="error" role="alert">{{ error }} <el-button link :disabled="busy" @click="open = false; emit('refresh')">刷新详情</el-button></p>
      <el-button :disabled="busy" @click="open = false">取消</el-button>
      <el-button type="danger" native-type="submit" :loading="busy">确认删除</el-button>
    </el-form>
  </el-dialog>
</template>
