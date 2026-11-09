<script setup lang="ts">
import { ref, watch, onScopeDispose } from 'vue'
import { ElMessage } from 'element-plus'
import { isAxiosError } from 'axios'
import { createTarget, listTargets, updateTarget, platformLabel, type ReleaseTarget } from '@/api/targetReleases'
import ErrorState from '@/components/ui/ErrorState.vue'
const props = defineProps<{ systemId: number; systemName: string }>()
const rows = ref<ReleaseTarget[]>([])
const failed = ref(false)
const loading = ref(false)
const editor = ref(false)
const busy = ref(false)
const current = ref<ReleaseTarget | null>(null)
const error = ref('')
const targetForm = ref({ code: '', name: '', platform: 'WECHAT_MINI_PROGRAM' as ReleaseTarget['platform'], app_id: '', url: '', enabled: true })
let sequence = 0
async function load() {
  const seq = ++sequence; loading.value = true; failed.value = false
  try { const items = await listTargets(props.systemId); if (seq === sequence) rows.value = items }
  catch { if (seq === sequence) failed.value = true }
  finally { if (seq === sequence) loading.value = false }
}
onScopeDispose(() => { sequence++ })
watch(() => props.systemId, () => { editor.value = false; void load() }, { immediate: true })
function edit(item: ReleaseTarget | null) {
  current.value = item; error.value = ''
  Object.assign(targetForm.value, item ?? { code: '', name: '', platform: 'WECHAT_MINI_PROGRAM', app_id: '', url: '', enabled: true })
  editor.value = true
}
async function save() {
  if (busy.value) return
  if (!targetForm.value.code.trim() || !targetForm.value.name.trim()) { error.value = '请填写目标名称和编码'; return }
  busy.value = true; error.value = ''
  try {
    const values = { ...targetForm.value, code: targetForm.value.code.trim(), name: targetForm.value.name.trim(), app_id: targetForm.value.app_id?.trim() || null, url: targetForm.value.url?.trim() || null }
    if (current.value) await updateTarget(current.value.id, { ...values, revision: current.value.revision })
    else await createTarget(props.systemId, values)
    editor.value = false; ElMessage.success('发布目标已保存'); await load()
  } catch (e) {
    error.value = isAxiosError(e) ? e.response?.data?.message || '保存失败，请检查输入' : '保存失败'
    if (isAxiosError(e) && e.response?.status === 409 && e.response?.data?.code === 40910) { editor.value = false; await load(); ElMessage.warning('目标已修改，请重新打开编辑') }
  } finally { busy.value = false }
}
</script>
<template>
  <div v-loading="loading" class="targets">
    <p>为 {{ systemName }} 维护具体站点或小程序。停用后保留历史发布记录；无需填写 AppSecret。</p>
    <el-button type="primary" @click="edit(null)">新增发布目标</el-button>
    <ErrorState v-if="failed" title="发布目标加载失败" retry-label="重新加载" @retry="load" />
    <article v-for="target in rows" :key="target.id" class="target">
      <div><strong>{{ target.name }}</strong><span>{{ platformLabel[target.platform] }} · {{ target.code }} · {{ target.enabled ? '启用' : '停用' }}</span><small v-if="target.app_id">AppID：{{ target.app_id }}</small><small v-if="target.url">{{ target.url }}</small></div>
      <el-button @click="edit(target)" :aria-label="`编辑发布目标 ${target.name}`">编辑</el-button>
    </article>
    <p v-if="!loading && !failed && !rows.length">暂无发布目标，可先添加本次需要发布的小程序。</p>
    <el-dialog v-model="editor" :title="current ? '编辑发布目标' : '新增发布目标'" width="min(540px, calc(100vw - 24px))" append-to-body :close-on-click-modal="!busy">
      <el-form label-position="top" @submit.prevent="save">
        <el-form-item label="目标名称" required><el-input v-model="targetForm.name" maxlength="100" placeholder="如：品牌 A 小程序" /></el-form-item>
        <el-form-item label="目标编码" required><el-input v-model="targetForm.code" maxlength="64" placeholder="如 MINI_A" /></el-form-item>
        <el-form-item label="平台"><el-select v-model="targetForm.platform"><el-option v-for="(label, key) in platformLabel" :key="key" :value="key" :label="label" /></el-select></el-form-item>
        <el-form-item label="AppID（选填）"><el-input v-model="targetForm.app_id" maxlength="64" /></el-form-item>
        <el-form-item label="访问地址（选填）"><el-input v-model="targetForm.url" maxlength="500" placeholder="https://" /></el-form-item>
        <el-form-item label="状态"><el-switch v-model="targetForm.enabled" active-text="启用" inactive-text="停用" /></el-form-item>
        <el-alert v-if="error" :title="error" type="error" :closable="false" />
      </el-form>
      <template #footer><el-button :disabled="busy" @click="editor = false">取消</el-button><el-button type="primary" :loading="busy" @click="save">保存目标</el-button></template>
    </el-dialog>
  </div>
</template>
<style scoped>
.targets p { color: var(--if-text-2); line-height: 1.6; }
.target { display:flex; justify-content:space-between; gap:12px; align-items:center; padding:14px 0; border-bottom:1px solid var(--if-border); }
.target div { min-width:0; overflow-wrap:anywhere; }
.target span,.target small { display:block; margin-top:6px; color:var(--if-text-2); }
</style>
