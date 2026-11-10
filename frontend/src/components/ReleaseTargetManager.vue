<script setup lang="ts">
import { computed, ref, watch, onScopeDispose } from 'vue'
import { ElMessage } from 'element-plus'
import { isAxiosError } from 'axios'
import { createTarget, createMiniProgramTarget, listTargets, updateMiniProgramTarget, updateTarget, platformLabel, type ReleaseTarget } from '@/api/targetReleases'
import { groupReleaseTargets, type ReleaseTargetGroup, type MiniProgramPlatform } from '@/utils/releaseTargetGroups'
import ErrorState from '@/components/ui/ErrorState.vue'
const props = defineProps<{ systemId: number; systemName: string }>()
const rows = ref<ReleaseTarget[]>([])
const groups = computed(() => groupReleaseTargets(rows.value))
const failed = ref(false)
const loading = ref(false)
const editor = ref(false)
const busy = ref(false)
const current = ref<ReleaseTargetGroup | null>(null)
const error = ref('')
const miniPlatforms: MiniProgramPlatform[] = ['WECHAT_MINI_PROGRAM', 'ALIPAY_MINI_PROGRAM']
const targetForm = ref({ code: '', name: '', kind: 'MINI_PROGRAM', url: '', enabled: true,
  WECHAT_MINI_PROGRAM: { enabled: true, app_id: '' }, ALIPAY_MINI_PROGRAM: { enabled: false, app_id: '' } })
let sequence = 0
async function load() {
  const seq = ++sequence; rows.value = []; loading.value = true; failed.value = false
  try { const items = await listTargets(props.systemId); if (seq === sequence) rows.value = items }
  catch { if (seq === sequence) failed.value = true }
  finally { if (seq === sequence) loading.value = false }
}
onScopeDispose(() => { sequence++ })
watch(() => props.systemId, () => { editor.value = false; void load() }, { immediate: true })
function edit(group: ReleaseTargetGroup | null) {
  current.value = group; error.value = ''
  const member = (platform: MiniProgramPlatform) => group?.members.find(t => t.platform === platform)
  targetForm.value = {
    code: group?.code ?? '', name: group?.name ?? '', kind: group?.kind ?? 'MINI_PROGRAM',
    url: group?.members[0]?.url ?? '', enabled: group?.members[0]?.enabled ?? true,
    WECHAT_MINI_PROGRAM: { enabled: member('WECHAT_MINI_PROGRAM')?.enabled ?? !group, app_id: member('WECHAT_MINI_PROGRAM')?.app_id ?? '' },
    ALIPAY_MINI_PROGRAM: { enabled: member('ALIPAY_MINI_PROGRAM')?.enabled ?? false, app_id: member('ALIPAY_MINI_PROGRAM')?.app_id ?? '' },
  }
  editor.value = true
}
async function save() {
  if (busy.value) return
  const form = targetForm.value
  if (!form.code.trim() || !form.name.trim()) { error.value = '请填写目标名称和编码'; return }
  const platforms = miniPlatforms.filter(platform => form[platform].enabled || current.value?.members.some(t => t.platform === platform))
  if (form.kind === 'MINI_PROGRAM') {
    if (!platforms.length) { error.value = '请至少配置微信或支付宝中的一个平台'; return }
    if (form.code.trim().length > 57) { error.value = '小程序品牌编码最多 57 个字符，请缩短编码'; return }
    for (const platform of platforms) {
      if (form[platform].enabled && !form[platform].app_id.trim() && !current.value?.members.some(t => t.platform === platform && !t.app_id)) {
        error.value = `请填写${platformLabel[platform]} AppID`; return
      }
    }
  }
  busy.value = true; error.value = ''
  const savedSystem = props.systemId
  try {
    const common = { code: form.code.trim(), name: form.name.trim() }
    if (form.kind === 'PC_WEB') {
      const values = { ...common, platform: 'PC_WEB' as const, app_id: null, url: form.url.trim() || null, enabled: form.enabled }
      if (current.value) await updateTarget(current.value.members[0].id, { ...values, revision: current.value.members[0].revision })
      else await createTarget(props.systemId, values)
    } else {
      const values = { ...common, platforms: platforms.map(platform => ({ platform, app_id: form[platform].app_id.trim() || null, enabled: form[platform].enabled })) }
      if (current.value) await updateMiniProgramTarget(current.value.members[0].id, { ...values, members: current.value.members.map(({ id, revision }) => ({ id, revision })) })
      else await createMiniProgramTarget(props.systemId, values)
    }
    if (props.systemId !== savedSystem) return
    editor.value = false; ElMessage.success('发布目标已保存'); await load()
  } catch (e) {
    if (props.systemId !== savedSystem) return
    error.value = isAxiosError(e) ? e.response?.data?.message || '保存失败，请检查输入' : '保存失败'
    if (isAxiosError(e) && e.response?.status === 409 && e.response?.data?.code === 40910) {
      editor.value = false; await load(); ElMessage.warning('平台配置已修改，请重新打开编辑')
    }
  } finally { busy.value = false }
}
</script>
<template>
  <div v-loading="loading" class="targets">
    <p>为 {{ systemName }} 维护发布目标。同一小程序品牌统一配置微信与支付宝，发布时可分别勾选平台。</p>
    <el-button type="primary" :disabled="loading || failed" @click="edit(null)">新增发布目标</el-button>
    <ErrorState v-if="failed" title="发布目标加载失败" retry-label="重新加载" @retry="load" />
    <article v-for="group in groups" :key="group.key" class="target">
      <header><div><strong>{{ group.name }}</strong><span>{{ group.kind === 'PC_WEB' ? 'PC Web' : '小程序' }} · {{ group.code }}</span></div><el-button @click="edit(group)" :aria-label="`编辑发布目标 ${group.name}`">编辑</el-button></header>
      <div class="platform-summary">
        <div v-for="target in group.members" :key="target.id"><span>{{ platformLabel[target.platform] }} · {{ target.enabled ? '启用' : '停用' }}</span><small>{{ target.platform === 'PC_WEB' ? target.url || '暂未填写访问地址' : `AppID：${target.app_id || '暂未填写'}` }}</small></div>
      </div>
    </article>
    <p v-if="!loading && !failed && !groups.length">暂无发布目标，可先添加本次需要发布的小程序或 PC 站点。</p>
    <el-dialog v-model="editor" :title="current ? '编辑发布目标' : '新增发布目标'" width="min(680px, calc(100vw - 24px))" append-to-body :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
      <el-form label-position="top" :disabled="busy" @submit.prevent="save">
        <el-form-item label="目标名称" required><el-input v-model="targetForm.name" maxlength="100" placeholder="如：开电" /></el-form-item>
        <el-form-item label="目标编码" required><el-input v-model="targetForm.code" :maxlength="targetForm.kind === 'MINI_PROGRAM' ? 57 : 64" placeholder="如 MINI_A" /></el-form-item>
        <el-form-item label="目标类型"><el-radio-group v-model="targetForm.kind" :disabled="!!current"><el-radio-button value="MINI_PROGRAM">小程序</el-radio-button><el-radio-button value="PC_WEB">PC Web</el-radio-button></el-radio-group></el-form-item>
        <div v-if="targetForm.kind === 'MINI_PROGRAM'" class="platform-configs">
          <section v-for="platform in miniPlatforms" :key="platform" class="platform-config" :aria-label="`${platformLabel[platform]}配置`">
            <el-checkbox v-model="targetForm[platform].enabled" :aria-label="`启用${platformLabel[platform]}`">{{ platformLabel[platform] }}</el-checkbox>
            <el-form-item :label="`${platformLabel[platform]} AppID`"><el-input v-model="targetForm[platform].app_id" maxlength="64" :disabled="!targetForm[platform].enabled" :placeholder="platform === 'WECHAT_MINI_PROGRAM' ? 'wx 开头的 AppID' : '支付宝 AppID'" /></el-form-item>
            <p>{{ targetForm[platform].enabled ? '发布时可单独勾选并记录上线时间。' : '未启用；已有发布历史会保留。' }}</p>
          </section>
        </div>
        <template v-else><el-form-item label="访问地址（选填）"><el-input v-model="targetForm.url" maxlength="500" placeholder="https://" /></el-form-item><el-form-item label="状态"><el-switch v-model="targetForm.enabled" active-text="启用" inactive-text="停用" /></el-form-item></template>
        <el-alert v-if="error" :title="error" type="error" :closable="false" />
      </el-form>
      <template #footer><el-button :disabled="busy" @click="editor = false">取消</el-button><el-button type="primary" :loading="busy" @click="save">保存目标</el-button></template>
    </el-dialog>
  </div>
</template>
<style scoped>
.targets p { color:var(--if-text-2); line-height:1.6; }
.target { margin-top:16px; border:1px solid var(--if-border); border-radius:12px; padding:16px; overflow-wrap:anywhere; }
.target header { display:flex; justify-content:space-between; gap:12px; align-items:center; }
.target header div { min-width:0; }
.target header span,.target small { display:block; margin-top:6px; color:var(--if-text-2); }
.platform-summary,.platform-configs { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }
.platform-summary { margin-top:16px; font-size:13px; }
.platform-config { border:1px solid var(--if-border); border-radius:12px; padding:12px; min-width:0; }
.platform-config :deep(.el-checkbox) { min-height:44px; margin:0; }
.platform-config :deep(.el-form-item) { margin:8px 0; }
.platform-config p { font-size:12px; margin:0; line-height:1.6; }
@media (max-width:600px) { .platform-configs,.platform-summary { grid-template-columns:1fr; } }
</style>
