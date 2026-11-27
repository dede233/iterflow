<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { isAxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import { getUserWecomBinding, updateUserWecomBinding, type WecomPreferences } from '@/api/wecom'
import { conflictReadError, isRevisionConflict } from '@/types/revisionConflict'
import type { UserItem } from '@/types/system'

const visible = defineModel<boolean>({ required: true })
const props = defineProps<{ user: UserItem }>()

const binding = ref<WecomPreferences>()
const memberId = ref('')
const loading = ref(false)
const saving = ref(false)
const refreshRequired = ref(false)
const readError = ref('')
const writeError = ref('')
const trimmedMemberId = computed(() => memberId.value.trim())
const newMemberId = computed(() => trimmedMemberId.value || null)
const invalidMemberId = computed(() => Boolean(
  trimmedMemberId.value && !/^[A-Za-z0-9_][A-Za-z0-9_.@-]{0,63}$/.test(trimmedMemberId.value),
))
const canSave = computed(() =>
  Boolean(binding.value && newMemberId.value !== binding.value.member_user_id &&
    (newMemberId.value === null || props.user.status === 'ACTIVE') &&
    !invalidMemberId.value && !loading.value && !saving.value && !refreshRequired.value),
)

async function load(): Promise<void> {
  if (loading.value || saving.value) return
  const preserveInput = refreshRequired.value
  loading.value = true
  readError.value = ''
  try {
    const latest = await getUserWecomBinding(props.user.id)
    binding.value = latest
    if (!preserveInput) memberId.value = latest.member_user_id ?? ''
    refreshRequired.value = false
    writeError.value = ''
  } catch (cause) {
    readError.value = conflictReadError(cause)
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  if (!binding.value || !canSave.value) return
  saving.value = true
  writeError.value = ''
  try {
    const updated = await updateUserWecomBinding(props.user.id, {
      revision: binding.value.revision,
      member_user_id: newMemberId.value,
    })
    ElMessage.success(updated.member_user_id ? '企业微信成员绑定已保存。' : '企业微信成员绑定已解除。')
    visible.value = false
  } catch (cause) {
    if (isRevisionConflict(cause)) {
      refreshRequired.value = true
      writeError.value = '成员绑定或通知偏好已变更。请刷新后核对当前绑定，输入会保留。'
      return
    }
    const status = isAxiosError(cause) ? cause.response?.status : undefined
    if (status === 409) {
      writeError.value = '无法保存成员绑定，请核对迭程账号状态和企业微信成员账号。'
    } else if (status === 403 || status === 404) {
      refreshRequired.value = true
      writeError.value = '该用户已不可操作，请刷新后核对权限和账号状态。'
    } else {
      writeError.value = '未能确认绑定已保存，请稍后重试。'
    }
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <el-dialog
    v-model="visible"
    title="企业微信成员绑定"
    width="min(500px, calc(100vw - 32px))"
    :close-on-click-modal="false"
    :close-on-press-escape="!saving"
    :show-close="!saving"
  >
    <div class="binding-body" :aria-busy="loading || saving">
      <p class="binding-user"><strong>{{ user.display_name }}</strong> <span>@{{ user.username }}</span></p>
      <p v-if="loading && !binding" role="status">正在加载成员绑定…</p>
      <el-alert v-if="readError" :title="readError" type="warning" show-icon :closable="false" />
      <el-alert v-if="writeError" :title="writeError" type="warning" show-icon :closable="false" />
      <el-form v-if="binding" label-position="top" @submit.prevent="save">
        <dl class="binding-current">
          <dt>当前绑定</dt>
          <dd>{{ binding.member_user_id || '未绑定' }}</dd>
        </dl>
        <el-form-item
          label="企业微信成员账号（UserID）"
          :error="invalidMemberId ? '请输入有效的企业微信成员账号。' : ''"
        >
          <el-input
            v-model="memberId"
            :disabled="loading || saving || (user.status === 'DISABLED' && !binding.member_user_id)"
            autocomplete="off"
            aria-describedby="wecom-binding-help"
          />
        </el-form-item>
        <p id="wecom-binding-help" class="binding-note">填写企业微信通讯录中的成员账号。变更绑定后，用户需重新开启企业微信通知。</p>
        <p v-if="user.status === 'DISABLED'" class="binding-note">迭程账号已停用，启用后可绑定企业微信成员。</p>
        <p v-if="binding.member_user_id" class="binding-note">清空成员账号后可解除绑定。</p>
      </el-form>
    </div>
    <template #footer>
      <el-button :disabled="saving" @click="visible = false">取消</el-button>
      <el-button v-if="refreshRequired || readError" :loading="loading" @click="load">刷新绑定</el-button>
      <el-button v-if="binding" :type="newMemberId === null ? 'danger' : 'primary'" :loading="saving" :disabled="!canSave" @click="save">
        {{ newMemberId === null && binding.member_user_id ? '解除绑定' : '保存绑定' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.binding-body { display: grid; gap: 12px; }
.binding-user, .binding-current { margin: 0; overflow-wrap: anywhere; }
.binding-user span, .binding-current dt, .binding-note { color: var(--if-text-2); }
.binding-current { display: flex; flex-wrap: wrap; gap: 4px 12px; }
.binding-current dd { min-width: 0; margin: 0; }
.binding-body .el-form-item { margin-top: 16px; }
.binding-note { margin: 8px 0 0; }

@media (max-width: 767px) {
  .binding-body :deep(.el-input__wrapper) { min-height: 44px; }
}
</style>
