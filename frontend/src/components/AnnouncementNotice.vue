<script setup lang="ts">
import { computed, onMounted, onScopeDispose, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAnnouncementsStore } from '@/stores/announcements'
const props = defineProps<{ blocked?: boolean }>()
const auth = useAuthStore(), notices = useAnnouncementsStore(), route = useRoute(), router = useRouter()
const dismissed = ref(false), dialogDismissed = ref(false), busy = ref(false), error = ref('')
const visible = computed(() => !props.blocked && !route.path.startsWith('/announcements') && !auth.mustChangePassword && !dismissed.value && notices.unreadCount > 0)
const dialogVisible = computed(() => visible.value && !dialogDismissed.value && !!notices.important)
async function refresh() { if (!auth.mustChangePassword) await notices.refresh() }
watch(() => auth.user?.id, () => { notices.reset(); dismissed.value = false; dialogDismissed.value = false; void refresh() }, { immediate: true })
function focus() { void refresh() }
onMounted(() => window.addEventListener('focus', focus))
onScopeDispose(() => window.removeEventListener('focus', focus))
function open() { dialogDismissed.value = true; void router.push(`/announcements/${(notices.important || notices.latest)?.id}`) }
async function acknowledge() {
  const item = notices.important
  if (!item || busy.value) return
  busy.value = true; error.value = ''
  try { await notices.read(item); dialogDismissed.value = true }
  catch { error.value = '未能保存已读状态，请刷新后重试。'; await refresh() }
  finally { busy.value = false }
}
</script>
<template>
  <aside v-if="visible" class="announcement-banner" aria-label="更新公告提醒">
    <span>有 {{ notices.unreadCount }} 条未读更新公告</span>
    <el-button text type="primary" @click="open">查看更新</el-button>
    <el-button text aria-label="暂时关闭更新提醒" @click="dismissed = true">关闭</el-button>
  </aside>
  <el-dialog :model-value="dialogVisible" title="重要更新公告" width="min(480px, calc(100vw - 24px))" :close-on-click-modal="false"
    :close-on-press-escape="!busy" :show-close="!busy" @update:model-value="dialogDismissed = true">
    <h2>{{ notices.important?.title }}</h2>
    <p>{{ notices.important?.version_label }} · {{ notices.important?.release_date }}</p>
    <p>本次更新涉及使用流程或需要你注意的事项，请查看完整公告。</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <template #footer>
      <el-button :loading="busy" @click="acknowledge">我已知晓</el-button>
      <el-button type="primary" :disabled="busy" @click="open">查看详情</el-button>
    </template>
  </el-dialog>
</template>
<style scoped>
.announcement-banner { display:flex; align-items:center; flex-wrap:wrap; gap:8px; margin:12px 24px 0; padding:8px 12px; border:1px solid var(--if-border); border-radius:8px; background:var(--el-color-primary-light-9); font-size:14px; }
.announcement-banner span { flex:1; }
h2 { font-size:18px; overflow-wrap:anywhere; }
p { line-height:1.7; }
@media(max-width:767px) { .announcement-banner { margin:12px 12px 0; } }
</style>
