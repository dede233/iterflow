<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { versionTargets, platformLabel, type ReleaseTarget } from '@/api/targetReleases'
import { groupReleaseTargets } from '@/utils/releaseTargetGroups'
const props = defineProps<{ versionId: number; systemId?: number | null; active: boolean; disabled?: boolean }>()
const selected = defineModel<number[]>({ required: true })
const emit = defineEmits<{ ready: [ready: boolean] }>()
const targets = ref<ReleaseTarget[]>([])
const loading = ref(false)
const failed = ref(false)
const search = ref('')
const groups = computed(() => groupReleaseTargets(targets.value).filter(group =>
  `${group.name} ${group.code} ${group.members.map(t => t.app_id || '').join(' ')}`.toLowerCase().includes(search.value.toLowerCase())))
let sequence = 0
async function load() {
  const seq = ++sequence; targets.value = []; failed.value = false; loading.value = true; emit('ready', false)
  try {
    const data = await versionTargets(props.versionId, props.systemId)
    if (seq !== sequence) return
    targets.value = data; emit('ready', true)
  } catch { if (seq === sequence) failed.value = true }
  finally { if (seq === sequence) loading.value = false }
}
watch(() => [props.versionId, props.systemId, props.active], () => {
  sequence++; selected.value = []; search.value = ''; emit('ready', false)
  if (props.active) void load()
}, { immediate: true })
onScopeDispose(() => { sequence++ })
function toggle(id: number, checked: boolean) {
  if (props.disabled || loading.value || failed.value) return
  const target = targets.value.find(t => t.id === id)
  if (!target || target.covered || (checked && selected.value.length >= 50 && !selected.value.includes(id))) return
  selected.value = checked ? [...new Set([...selected.value, id])] : selected.value.filter(value => value !== id)
}
</script>
<template>
  <div v-loading="loading" class="coverage-select">
    <el-input v-model="search" placeholder="搜索小程序或 PC 名称、编码" aria-label="搜索已发布目标" clearable :disabled="disabled" />
    <div class="target-choices">
      <section v-for="group in groups" :key="group.key" class="target-group" :aria-label="`${group.name}发布平台`">
        <strong v-if="group.members.length > 1">{{ group.name }}</strong>
        <el-checkbox v-for="target in group.members" :key="target.id"
        :aria-label="`${target.name} · ${platformLabel[target.platform]}${target.covered ? '（已记录）' : ''}`"
        :model-value="target.covered || selected.includes(target.id)" :disabled="disabled || target.covered || (selected.length >= 50 && !selected.includes(target.id))"
        @change="(value: string | number | boolean) => toggle(target.id, !!value)">
        <template v-if="group.members.length === 1">{{ target.name }} · </template>{{ platformLabel[target.platform] }}<span v-if="target.covered">（已记录）</span>
      </el-checkbox>
      </section>
    </div>
    <el-button v-if="failed" link type="danger" :disabled="disabled" @click="load">目标加载失败，重试</el-button>
    <p v-else-if="!loading && !targets.length" class="hint">暂无启用目标，请联系管理员在业务系统中维护小程序或 PC 目标；也可以先发布版本，稍后补记。</p>
    <p v-else-if="!loading && targets.length && !groups.length" class="hint">没有匹配的目标，请调整搜索词。</p>
    <p class="hint">按平台勾选已经实际发布的小程序或 PC，可分别补记不同上线时间；已记录平台保留历史。当前新选 {{ selected.length }} 个平台 / 站点。</p>
  </div>
</template>
<style scoped>
.coverage-select { width:100%; min-width:0; }
.target-choices { display:flex; flex-direction:column; max-height:240px; overflow-y:auto; padding:8px 0; }
.target-group { display:flex; flex-direction:column; padding:8px 0; border-bottom:1px solid var(--if-border); }
.target-group strong { font-size:14px; line-height:1.6; margin:0 0 4px; }
.target-choices :deep(.el-checkbox) { margin:0; height:auto; min-height:44px; white-space:normal; }
.target-choices :deep(.el-checkbox__label) { overflow-wrap:anywhere; }
.hint { color:var(--if-text-3); font-size:13px; line-height:1.6; margin:8px 0; }
</style>
