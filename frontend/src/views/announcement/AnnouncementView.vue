<script setup lang="ts">
import { computed, onScopeDispose, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/api/client'
import { useAnnouncementsStore, type Announcement } from '@/stores/announcements'
import type { components } from '@/types/openapi.generated'
import RichTextContent from '@/components/RichTextContent.vue'
import RichTextEditor from '@/components/RichTextEditor.vue'
import { withDescriptionImages } from '@/utils/requirementImages'
const auth = useAuthStore()
const route = useRoute(), router = useRouter(), notices = useAnnouncementsStore()
const items = ref<Announcement[]>([]), item = ref<Announcement | null>(null), total = ref(0), page = ref(1)
const canManage = ref(false), manage = ref(false), busy = ref(false), loading = ref(false), error = ref('')
const editing = ref(false), preview = ref(false)
const form = reactive({ title:'', version_label:'', release_date:new Date().toLocaleDateString('en-CA'), content:'<p></p>', important:false })
const isDetail = computed(() => !!route.params.id)
let sequence = 0
onScopeDispose(() => { sequence++ })
async function load() {
  const request = ++sequence, userId = auth.user?.id
  loading.value = true; error.value = ''; item.value = null; editing.value = false
  try {
    const { data } = await api.get<components['schemas']['AnnouncementPage']>('/announcements', { params:{ page:page.value, page_size:20, manage:manage.value } })
    if (request !== sequence || userId !== auth.user?.id) return
    items.value = data.items; total.value = data.total; canManage.value = data.can_manage
    if (route.params.id) {
      const { data: detail } = await api.get<Announcement>(`/announcements/${route.params.id}`)
      if (request !== sequence || userId !== auth.user?.id) return
      item.value = detail
      if (detail.published_at && !detail.read_at) await notices.read(detail)
    }
    await notices.refresh()
  } catch { if (request === sequence) error.value = '公告加载失败，请重试。' }
  finally { if (request === sequence) loading.value = false }
}
watch(() => route.params.id, load, { immediate:true })
function edit(value: Announcement | null) {
  Object.assign(form, value ? {title:value.title, version_label:value.version_label, release_date:value.release_date, content:value.content, important:value.important}
    : {title:'',version_label:'',release_date:new Date().toLocaleDateString('en-CA'),content:'<p></p>',important:false})
  item.value = value; editing.value = true; error.value = ''
}
async function save() {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    const imagePayload = await withDescriptionImages({ description:form.content, description_format:'HTML' }) as {description_images?:Record<string,string>}
    const payload = {...form, image_uploads:imagePayload.description_images || {}}
    const result = item.value ? await api.patch<Announcement>(`/announcements/${item.value.id}`, {...payload, revision:item.value.revision})
      : await api.post<Announcement>('/announcements', payload)
    editing.value = false
    if (String(route.params.id) === String(result.data.id)) await load()
    else await router.push(`/announcements/${result.data.id}`)
  } catch (failure:any) { error.value = failure.response?.data?.message || failure.message || '保存失败，请重试。' }
  finally { busy.value = false }
}
async function publish() {
  if (!item.value || busy.value) return
  try { await ElMessageBox.confirm('请确认本环境已部署并验收本次更新。发布后所有登录用户可见；正式环境需另行发布公告。', '发布更新公告', {confirmButtonText:'确认发布',cancelButtonText:'取消'}) }
  catch { return }
  busy.value = true
  try { await api.post(`/announcements/${item.value.id}/publish`, {revision:item.value.revision}); await load() }
  catch (failure:any) { error.value = failure.response?.data?.message || '发布结果未确认，请刷新核对后再操作。' }
  finally { busy.value = false }
}
</script>
<template>
  <section class="announcement-page" v-loading="loading">
    <header><div><h1>更新公告</h1><p>了解迭程 IterFlow 的新增功能、体验优化与使用变化</p></div>
      <div class="actions"><router-link v-if="isDetail" to="/announcements">返回公告列表</router-link>
        <el-button v-if="canManage && !isDetail" @click="manage = !manage; page = 1; load()">{{ manage ? '查看已发布公告' : '管理草稿与公告' }}</el-button>
        <el-button v-if="canManage && !isDetail" type="primary" @click="edit(null)">新增公告</el-button>
      </div>
    </header>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <el-button v-if="error && !editing" @click="load">重新加载</el-button>
    <template v-if="!isDetail">
      <el-empty v-if="!loading && !items.length" description="暂无更新公告" />
      <article v-for="entry in items" :key="entry.id" class="notice-card">
        <div class="meta"><span>{{ entry.release_date }} · {{ entry.version_label }}</span><el-tag v-if="!entry.published_at" type="info">草稿</el-tag><el-tag v-else-if="!entry.read_at">未读</el-tag><el-tag v-if="entry.important" type="warning">重要更新</el-tag></div>
        <router-link :to="`/announcements/${entry.id}`"><h2>{{ entry.title }}</h2></router-link>
        <el-button text type="primary" @click="router.push(`/announcements/${entry.id}`)">查看详情</el-button>
      </article>
      <el-pagination v-if="total > 20" v-model:current-page="page" :page-size="20" :total="total" layout="prev, pager, next" @current-change="load" />
    </template>
    <article v-else-if="item" class="notice-card">
      <div class="meta">{{ item.release_date }} · {{ item.version_label }} <el-tag v-if="!item.published_at" type="info">草稿 · 仅管理员可见</el-tag><el-tag v-if="item.important" type="warning">重要更新</el-tag></div>
      <h2>{{ item.title }}</h2><RichTextContent :content="item.content" format="HTML" :announcement-id="item.id" />
      <div v-if="canManage" class="actions detail-actions"><el-button @click="edit(item)">编辑公告</el-button><el-button v-if="!item.published_at" type="primary" :loading="busy" @click="publish">发布公告</el-button></div>
    </article>
    <el-dialog v-model="editing" :title="item ? '编辑更新公告' : '新增更新公告'" width="min(900px, calc(100vw - 24px))" :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy">
      <el-alert v-if="item?.published_at" title="修正内容不会让已读用户重新变成未读；重大新事项请另建公告。" type="info" :closable="false" />
      <el-form label-position="top" @submit.prevent="save">
        <el-form-item label="公告标题"><el-input v-model="form.title" maxlength="200" /></el-form-item>
        <div class="form-row"><el-form-item label="版本标识"><el-input v-model="form.version_label" maxlength="100" placeholder="例如：2026.11 更新" /></el-form-item>
        <el-form-item label="上线日期"><el-input v-model="form.release_date" type="date" /></el-form-item></div>
        <el-form-item><el-checkbox v-model="form.important">重要更新：涉及流程变化或需要用户配合，登录后弹出提醒</el-checkbox></el-form-item>
        <el-form-item label="公告内容"><RichTextEditor v-model="form.content" label="公告内容" :announcement-id="item?.id" :disabled="busy" /></el-form-item>
        <p class="hint">建议按新增功能、体验优化、问题修复、需要注意组织内容；支持粘贴截图和插入本地图片。</p>
        <p v-if="error" role="alert">{{ error }}</p>
      </el-form>
      <template #footer><div class="actions"><el-button :disabled="busy" @click="preview = true">预览</el-button><el-button :disabled="busy" @click="editing = false">取消</el-button><el-button type="primary" :loading="busy" @click="save">{{ item?.published_at ? '保存修正' : '保存草稿' }}</el-button></div></template>
    </el-dialog>
    <el-dialog v-model="preview" title="公告预览" width="min(800px, calc(100vw - 24px))" append-to-body>
      <h2>{{ form.title || '公告标题' }}</h2><p>{{ form.release_date }} · {{ form.version_label }}</p><RichTextContent :content="form.content" format="HTML" :announcement-id="item?.id" />
    </el-dialog>
  </section>
</template>
<style scoped>
.announcement-page { padding:24px 32px; max-width:1200px; margin:auto; }
header { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; margin-bottom:24px; }
h1 { font-size:24px; margin:0 0 8px; } h2 { font-size:20px; overflow-wrap:anywhere; margin:16px 0; }
header p,.hint,.meta { color:var(--if-text-3); font-size:13px; line-height:1.7; }
.meta,.actions { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }.actions .el-button { margin:0; }
.notice-card { background:var(--if-bg-surface,#fff); border:1px solid var(--if-border); border-radius:12px; padding:24px; margin:16px 0; overflow-wrap:anywhere; }
.detail-actions { margin-top:24px; }.form-row { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
@media(max-width:767px) { .announcement-page { padding:16px 12px 90px; }.notice-card { padding:16px; }.form-row { grid-template-columns:1fr;gap:0; }.actions .el-button { min-height:44px; } }
</style>
