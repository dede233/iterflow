<script setup lang="ts">
import { computed, nextTick, ref, watch, onScopeDispose, useId } from 'vue'
import { ElMessage } from 'element-plus'
import { isAxiosError } from 'axios'
import { createTarget, createMiniProgramTarget, listTargets, updateMiniProgramTarget, updateTarget, platformLabel, type ReleaseTarget } from '@/api/targetReleases'
import { groupReleaseTargets, type ReleaseTargetGroup, type MiniProgramPlatform } from '@/utils/releaseTargetGroups'
import ErrorState from '@/components/ui/ErrorState.vue'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
const props = defineProps<{ systemId: number; systemName: string }>()
const rows = ref<ReleaseTarget[]>([])
const groups = computed(() => groupReleaseTargets(rows.value))
const search = ref('')
const statusFilter = ref('ALL')
const directoryFilters = [
  { label: '全部配置', value: 'ALL' }, { label: '有启用平台', value: 'ENABLED' },
  { label: '有停用平台', value: 'DISABLED' }, { label: '待补充配置', value: 'MISSING' },
]
function member(group: ReleaseTargetGroup, platform: MiniProgramPlatform) { return group.members.find(t => t.platform === platform) }
const filteredGroups = computed(() => groups.value.filter(group => {
  const matches = `${group.name} ${group.code} ${group.members.map(t => `${t.app_id ?? ''} ${t.url ?? ''}`).join(' ')}`.toLowerCase().includes(search.value.trim().toLowerCase())
  if (!matches) return false
  if (statusFilter.value === 'MISSING') return group.kind === 'MINI_PROGRAM' && miniPlatforms.some(p => !member(group, p) || !member(group, p)?.app_id)
  if (statusFilter.value === 'DISABLED') return group.members.some(t => !t.enabled)
  if (statusFilter.value === 'ENABLED') return group.members.some(t => t.enabled)
  return true
}))
const failed = ref(false)
const loading = ref(false)
const editor = ref(false)
const busy = ref(false)
const current = ref<ReleaseTargetGroup | null>(null)
const error = ref('')
const fieldErrors = ref<Record<string, string>>({})
const formElement = ref<HTMLElement>()
const errorPrefix = useId()
const savedForm = ref('')
const miniPlatforms: MiniProgramPlatform[] = ['WECHAT_MINI_PROGRAM', 'ALIPAY_MINI_PROGRAM']
const targetForm = ref({ code: '', name: '', kind: 'MINI_PROGRAM', url: '', enabled: true,
  WECHAT_MINI_PROGRAM: { enabled: true, app_id: '' }, ALIPAY_MINI_PROGRAM: { enabled: false, app_id: '' } })
const { requestLeave } = useUnsavedChanges({ isDirty: () => JSON.stringify(targetForm.value) !== savedForm.value,
  isBusy: () => busy.value, active: () => editor.value })
defineExpose({ requestClose: requestLeave })
async function closeEditor(done?: () => void) {
  if (!await requestLeave()) return
  if (done) done()
  else editor.value = false
}
function clearErrors() { fieldErrors.value = {} }
let sequence = 0
async function load() {
  const seq = ++sequence; rows.value = []; loading.value = true; failed.value = false
  try { const items = await listTargets(props.systemId); if (seq === sequence) rows.value = items }
  catch { if (seq === sequence) failed.value = true }
  finally { if (seq === sequence) loading.value = false }
}
onScopeDispose(() => { sequence++ })
watch(() => props.systemId, () => { editor.value = false; search.value = ''; statusFilter.value = 'ALL'; void load() }, { immediate: true })
function edit(group: ReleaseTargetGroup | null) {
  current.value = group; error.value = ''; clearErrors()
  const member = (platform: MiniProgramPlatform) => group?.members.find(t => t.platform === platform)
  targetForm.value = {
    code: group?.code ?? '', name: group?.name ?? '', kind: group?.kind ?? 'MINI_PROGRAM',
    url: group?.members[0]?.url ?? '', enabled: group?.members[0]?.enabled ?? true,
    WECHAT_MINI_PROGRAM: { enabled: member('WECHAT_MINI_PROGRAM')?.enabled ?? !group, app_id: member('WECHAT_MINI_PROGRAM')?.app_id ?? '' },
    ALIPAY_MINI_PROGRAM: { enabled: member('ALIPAY_MINI_PROGRAM')?.enabled ?? false, app_id: member('ALIPAY_MINI_PROGRAM')?.app_id ?? '' },
  }
  savedForm.value = JSON.stringify(targetForm.value); editor.value = true
}
function validateForm(): Record<string, string> {
  const form = targetForm.value
  const errors: Record<string, string> = {}
  if (!form.name.trim()) errors.name = '请填写目标名称'
  if (!form.code.trim()) errors.code = '请填写目标编码'
  const platforms = miniPlatforms.filter(platform => form[platform].enabled || current.value?.members.some(t => t.platform === platform))
  if (form.kind === 'MINI_PROGRAM') {
    if (!platforms.length) errors.platforms = '请至少配置微信或支付宝中的一个平台'
    if (form.code.trim().length > 57) errors.code = '小程序品牌编码最多 57 个字符，请缩短编码'
    for (const platform of platforms) {
      if (form[platform].enabled && !form[platform].app_id.trim() && !current.value?.members.some(t => t.platform === platform && !t.app_id)) {
        errors[platform] = `请填写${platformLabel[platform]} AppID`
      }
    }
  }
  return errors
}
watch(targetForm, () => {
  if (!Object.keys(fieldErrors.value).length) return
  const errors = validateForm()
  fieldErrors.value = Object.fromEntries(Object.keys(fieldErrors.value).filter(key => errors[key]).map(key => [key, errors[key]]))
}, { deep: true })
async function save() {
  if (busy.value) return
  const form = targetForm.value
  error.value = ''
  fieldErrors.value = validateForm()
  if (Object.keys(fieldErrors.value).length) {
    await nextTick()
    formElement.value?.querySelector<HTMLInputElement>('input[aria-invalid="true"]')?.focus()
    return
  }
  const platforms = miniPlatforms.filter(platform => form[platform].enabled || current.value?.members.some(t => t.platform === platform))
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
    <p class="directory-hint">{{ systemName }} · 共 {{ groups.length }} 个品牌 / 站点。小程序按品牌管理，微信与支付宝可分别记录发布时间。</p>
    <div class="directory-toolbar">
      <el-input v-model="search" aria-label="搜索发布目标" placeholder="搜索名称、编码或 AppID" clearable />
      <select v-model="statusFilter" class="directory-filter" aria-label="发布目标配置筛选">
        <option v-for="option in directoryFilters" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
      <el-button type="primary" :disabled="loading || failed" @click="edit(null)">新增发布目标</el-button>
    </div>
    <ErrorState v-if="failed" title="发布目标加载失败" retry-label="重新加载" @retry="load" />
    <div v-if="filteredGroups.length" class="target-directory" aria-label="品牌平台配置">
      <div class="directory-heading" aria-hidden="true"><span>品牌 / 站点</span><template v-if="filteredGroups.some(group => group.kind === 'MINI_PROGRAM')"><span>微信小程序</span><span>支付宝小程序</span></template><span v-else class="pc-site">PC Web 访问地址</span><span>操作</span></div>
      <article v-for="group in filteredGroups" :key="group.key" class="target" :aria-label="group.name">
        <header><strong>{{ group.name }}</strong><span>{{ group.kind === 'PC_WEB' ? 'PC Web' : '小程序' }} · {{ group.code }}</span></header>
        <template v-if="group.kind === 'MINI_PROGRAM'">
          <div v-for="platform in miniPlatforms" :key="platform" class="platform-cell" :aria-label="platformLabel[platform]">
            <span class="mobile-platform">{{ platformLabel[platform] }}</span>
            <span class="config-state" :class="{ enabled: member(group, platform)?.enabled }">{{ !member(group, platform) ? '未配置' : member(group, platform)?.enabled ? '启用' : '已停用' }}</span>
            <small v-if="member(group, platform)">AppID：{{ member(group, platform)?.app_id || '待补充' }}</small>
          </div>
        </template>
        <div v-else class="platform-cell pc-site"><span class="config-state" :class="{ enabled: group.members[0].enabled }">PC Web · {{ group.members[0].enabled ? '启用' : '已停用' }}</span><small>{{ group.members[0].url || '暂未填写访问地址' }}</small></div>
        <el-button class="edit-target" @click="edit(group)" :aria-label="`编辑发布目标 ${group.name}`">编辑</el-button>
      </article>
    </div>
    <p v-else-if="!loading && !failed && groups.length" role="status">没有符合条件的目标，请调整搜索或配置筛选。</p>
    <p v-if="!loading && !failed && !groups.length">暂无发布目标，可先添加本次需要发布的小程序或 PC 站点。</p>
    <el-dialog v-model="editor" :title="current ? '编辑发布目标' : '新增发布目标'" width="min(680px, calc(100vw - 24px))" append-to-body :before-close="closeEditor" :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
      <div ref="formElement">
      <el-form label-position="top" :disabled="busy" @submit.prevent="save">
        <el-form-item label="目标名称" required :class="{ 'has-field-error': fieldErrors.name }"><el-input v-model="targetForm.name" maxlength="100" placeholder="如：开电" :aria-invalid="!!fieldErrors.name" :aria-describedby="fieldErrors.name ? `${errorPrefix}-name` : undefined" /><p v-if="fieldErrors.name" :id="`${errorPrefix}-name`" class="field-error" role="alert">{{ fieldErrors.name }}</p></el-form-item>
        <el-form-item label="目标编码" required :class="{ 'has-field-error': fieldErrors.code }"><el-input v-model="targetForm.code" :maxlength="targetForm.kind === 'MINI_PROGRAM' ? 57 : 64" placeholder="如 MINI_A" :aria-invalid="!!fieldErrors.code" :aria-describedby="fieldErrors.code ? `${errorPrefix}-code` : undefined" /><p v-if="fieldErrors.code" :id="`${errorPrefix}-code`" class="field-error" role="alert">{{ fieldErrors.code }}</p></el-form-item>
        <el-form-item label="目标类型"><el-radio-group v-model="targetForm.kind" :disabled="!!current"><el-radio-button value="MINI_PROGRAM">小程序</el-radio-button><el-radio-button value="PC_WEB">PC Web</el-radio-button></el-radio-group></el-form-item>
        <div v-if="targetForm.kind === 'MINI_PROGRAM'" class="platform-configs">
          <section v-for="platform in miniPlatforms" :key="platform" class="platform-config" :aria-label="`${platformLabel[platform]}配置`">
            <el-checkbox v-model="targetForm[platform].enabled" :aria-label="`启用${platformLabel[platform]}`">{{ platformLabel[platform] }}</el-checkbox>
            <el-form-item :label="`${platformLabel[platform]} AppID`" :class="{ 'has-field-error': fieldErrors[platform] }"><el-input v-model="targetForm[platform].app_id" maxlength="64" :disabled="!targetForm[platform].enabled" :placeholder="platform === 'WECHAT_MINI_PROGRAM' ? 'wx 开头的 AppID' : '支付宝 AppID'" :aria-invalid="!!fieldErrors[platform]" :aria-describedby="fieldErrors[platform] ? `${errorPrefix}-${platform}` : undefined" /><p v-if="fieldErrors[platform]" :id="`${errorPrefix}-${platform}`" class="field-error" role="alert">{{ fieldErrors[platform] }}</p></el-form-item>
            <p>{{ targetForm[platform].enabled ? '发布时可单独勾选并记录上线时间。' : '未启用；已有发布历史会保留。' }}</p>
          </section>
        </div>
        <p v-if="targetForm.kind === 'MINI_PROGRAM' && fieldErrors.platforms" class="field-error" role="alert">{{ fieldErrors.platforms }}</p>
        <template v-if="targetForm.kind === 'PC_WEB'"><el-form-item label="访问地址（选填）"><el-input v-model="targetForm.url" maxlength="500" placeholder="https://" /></el-form-item><el-form-item label="状态"><el-switch v-model="targetForm.enabled" active-text="启用" inactive-text="停用" /></el-form-item></template>
        <el-alert v-if="error" :title="error" type="error" :closable="false" />
      </el-form>
      </div>
      <template #footer><el-button :disabled="busy" @click="closeEditor()">取消</el-button><el-button type="primary" :loading="busy" @click="save">保存目标</el-button></template>
    </el-dialog>
  </div>
</template>
<style scoped>
.targets p { color:var(--if-text-2); line-height:1.6; }
.directory-hint { margin:0 0 16px; font-size:13px; }
.directory-toolbar { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:16px; }
.directory-toolbar :deep(.el-input) { flex:1 1 210px; width:auto; }
.directory-filter { flex:0 1 145px; min-width:0; min-height:32px; border:1px solid var(--if-border); border-radius:var(--if-radius-xs); padding:4px 8px; background:var(--if-bg-surface); color:var(--if-text-2); font:inherit; font-size:14px; }
.directory-filter:focus-visible { outline:2px solid var(--if-brand-500); outline-offset:2px; }
.directory-toolbar :deep(.el-button) { margin:0; }
.target-directory { border:1px solid var(--if-border); border-radius:var(--if-radius); overflow:hidden; }
.directory-heading,.target { display:grid; grid-template-columns:minmax(130px,1fr) minmax(130px,1fr) minmax(130px,1fr) auto; gap:16px; align-items:start; }
.directory-heading { background:var(--if-bg-page); color:var(--if-text-2); font-size:13px; padding:12px 16px; }
.directory-heading span:last-child { min-width:60px; }
.target { padding:16px; overflow-wrap:anywhere; border-top:1px solid var(--if-border); }
.target header { min-width:0; }
.target header strong { font-size:14px; }
.target header span,.target small { display:block; margin-top:6px; color:var(--if-text-2); font-size:12px; line-height:1.6; }
.platform-cell { min-width:0; font-size:13px; }
.config-state { display:inline-flex; align-items:center; gap:5px; color:var(--if-text-3); }
.config-state.enabled { color:var(--if-success-fg); }
.config-state.enabled::before { content:''; width:5px; height:5px; border-radius:50%; background:currentColor; }
.pc-site { grid-column:span 2; }
.mobile-platform { display:none; }
.platform-configs { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }
.platform-config { border:1px solid var(--if-border); border-radius:12px; padding:12px; min-width:0; }
.platform-config :deep(.el-checkbox) { min-height:44px; margin:0; }
.platform-config :deep(.el-form-item) { margin:8px 0; }
.platform-config p { font-size:12px; margin:0; line-height:1.6; }
.field-error { color:var(--if-danger-fg) !important; font-size:13px; width:100%; margin:4px 0 0; line-height:1.5; }
.has-field-error :deep(.el-input__wrapper) { box-shadow:0 0 0 1px var(--if-danger-fg) inset; }
@media (max-width:767px) {
  .directory-heading { display:none; }
  .target-directory { border:0; border-radius:0; }
  .target { grid-template-columns:1fr auto; padding:16px; gap:12px; border:1px solid var(--if-border); border-radius:var(--if-radius); margin-bottom:12px; }
  .target header { grid-column:1; grid-row:1; }
  .edit-target { grid-column:2; grid-row:1; min-height:44px; }
  .platform-cell,.pc-site { grid-column:1 / -1; border-top:1px solid var(--if-border); padding-top:12px; }
  .mobile-platform { display:inline; margin-right:10px; }
  .platform-configs { grid-template-columns:1fr; }
  .directory-toolbar { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); }
  .directory-toolbar :deep(.el-input) { grid-column:1 / -1; width:100%; min-width:0; }
  .directory-toolbar :deep(.el-button) { width:100%; min-width:0; padding-inline:8px; }
  .directory-filter { width:100%; min-height:44px; }
  .directory-toolbar :deep(.el-input__wrapper),.directory-toolbar :deep(.el-button) { min-height:44px; }
}
</style>
