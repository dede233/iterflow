<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { isAxiosError } from 'axios'
import { getWecomPreferences, updateWecomPreferences, type WecomMode, type WecomPreferences } from '@/api/wecom'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { isRevisionConflict } from '@/types/revisionConflict'

const modeLabels: Record<WecomMode, string> = {
  OFF: '关闭',
  TASKS: '仅待办与上线',
  ALL: '全部关键通知',
}
const preferences = ref<WecomPreferences>()
const mode = ref<WecomMode>('OFF')
const loading = ref(false)
const saving = ref(false)
const refreshRequired = ref(false)
const error = ref('')
const message = ref('')
const bound = computed(() => Boolean(preferences.value?.member_user_id))
const canSave = computed(() =>
  Boolean(preferences.value?.enabled && mode.value !== preferences.value.mode &&
    (mode.value === 'OFF' || bound.value) && !loading.value && !saving.value && !refreshRequired.value),
)

async function load(): Promise<void> {
  if (loading.value || saving.value) return
  const preserveSelection = refreshRequired.value
  loading.value = true
  error.value = ''
  message.value = ''
  try {
    const latest = await getWecomPreferences()
    preferences.value = latest
    if (!preserveSelection) mode.value = latest.mode
    refreshRequired.value = false
  } catch {
    error.value = '企业微信通知设置加载失败，请重试。'
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  if (!preferences.value || !canSave.value) return
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    const updated = await updateWecomPreferences({ revision: preferences.value.revision, mode: mode.value })
    preferences.value = updated
    mode.value = updated.mode
    message.value = '企业微信通知偏好已保存。'
  } catch (cause) {
    if (isAxiosError(cause) && cause.response?.status === 409) {
      refreshRequired.value = true
      error.value = isRevisionConflict(cause)
        ? '企业微信通知设置已变更。请刷新后核对最新设置，所选偏好会保留。'
        : '当前账号无法启用所选偏好。请刷新并核对绑定状态。'
    } else {
      error.value = '未能确认偏好已保存，请稍后重试。'
    }
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <SectionCard v-if="preferences?.enabled" title="企业微信通知">
    <div class="wecom-settings" :aria-busy="loading || saving">
      <el-alert v-if="error" :title="error" type="warning" show-icon :closable="false" />
      <el-button v-if="refreshRequired" :loading="loading" @click="load">
        刷新设置
      </el-button>
      <el-form label-position="top" @submit.prevent="save">
        <div class="wecom-status">
          <StatusTag :status="bound ? 'BOUND' : 'UNBOUND'" :type="bound ? 'success' : 'info'" :label="bound ? '已绑定' : '未绑定'" />
          <span v-if="!bound">请联系超级管理员绑定企业微信成员账号。</span>
        </div>
        <el-form-item label="接收范围">
          <el-select v-model="mode" aria-label="接收范围" :disabled="loading || saving || (!bound && mode === 'OFF')">
            <el-option v-for="(label, value) in modeLabels" :key="value" :label="label" :value="value" :disabled="value !== 'OFF' && !bound" />
          </el-select>
        </el-form-item>
        <p v-if="mode !== preferences.mode" class="wecom-note">已保存的偏好为「{{ modeLabels[preferences.mode] }}」。</p>
        <el-button type="primary" native-type="submit" :loading="saving" :disabled="!canSave">保存企业微信偏好</el-button>
        <p v-if="message" class="wecom-note" role="status">{{ message }}</p>
      </el-form>
    </div>
  </SectionCard>
</template>

<style scoped>
.wecom-settings { display: grid; justify-items: start; gap: 12px; max-width: 560px; }
.wecom-settings .el-form, .wecom-settings .el-select { width: 100%; }
.wecom-settings .el-form-item { margin: 16px 0 12px; }
.wecom-status { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.wecom-note { margin: 8px 0; color: var(--if-text-2); }

@media (max-width: 767px) {
  .wecom-settings .el-button,
  .wecom-settings :deep(.el-select__wrapper) { min-height: 44px; }
}
</style>
