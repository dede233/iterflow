<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { components } from '@/types/openapi.generated'

const model = defineModel<number | null>({ default: null })
withDefaults(defineProps<{ currentName?: string | null; disabled?: boolean; clearable?: boolean }>(), { clearable: true })
const options = ref<components['schemas']['BusinessSystemOption'][]>([])
const loading = ref(false)
const failed = ref(false)
async function load() {
  loading.value = true; failed.value = false
  try { options.value = (await api.get('/systems/options')).data }
  catch { failed.value = true }
  finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <div class="system-select">
    <el-select v-model="model" :disabled="disabled" :clearable="clearable" filterable :loading="loading" placeholder="选择业务系统" style="width: 100%" @clear="model = null">
      <el-option v-if="model && !options.some(option => option.id === model)" :value="model" :label="currentName || `系统 #${model}`" disabled />
      <el-option v-for="option in options" :key="option.id" :label="option.name" :value="option.id" />
    </el-select>
    <el-button v-if="failed" link type="danger" @click="load">系统加载失败，重试</el-button>
    <span v-else-if="!loading && !options.length" class="hint">暂无可选系统，请联系管理员启用业务系统</span>
  </div>
</template>

<style scoped>
.system-select { width: 100%; min-width: 0; }
.hint { color: var(--if-text-3); font-size: 12px; }
</style>
