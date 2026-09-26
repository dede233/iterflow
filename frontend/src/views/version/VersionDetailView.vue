<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  addVersionRequirement,
  changeVersionStatus,
  checkVersionPublish,
  getVersion,
  listVersionRequirements,
  moveVersionRequirement,
  publishVersion,
  removeVersionRequirement,
  updateVersion,
} from '@/api/versions'
import { listReleases } from '@/api/releases'
import { getRequirement } from '@/api/requirements'
import { usePermission } from '@/composables/usePermission'
import { loadVersionDetailSections } from '@/security/detailAuthorization'
import StatusTag from '@/components/StatusTag.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import { useResponsive } from '@/composables/useResponsive'
import { formatLocalDateTime } from '@/utils/dates'
import {
  availableVersionStatusActions,
  versionRequirementSetFrozen,
  versionStatusLabel,
  versionStatusTagType,
  type VersionStatusAction,
} from '@/constants/version'
import { requirementStatusLabel, requirementStatusTagType } from '@/constants/requirement'
import type {
  PublishCheckItem,
  ReleaseItem,
  Requirement,
  VersionItem,
  VersionStats,
} from '@/types/domain'

const route = useRoute()
const router = useRouter()
const { can } = usePermission()
const { isMobile } = useResponsive()
const id = Number(route.params.id)

const item = ref<VersionItem | null>(null)
const requirements = ref<Requirement[]>([])
const stats = ref<VersionStats | null>(null)
const releases = ref<ReleaseItem[]>([])
const loading = ref(false)
const failed = ref(false)

const canEdit = computed(() => can('rd.version.edit'))
const canChangeStatus = computed(() => can('rd.version.status'))
const canViewRequirements = computed(() => can('rd.requirement.view'))
const canViewReleases = computed(() => can('rd.release.view'))
// Publish entry: only for a READY version and only with the publish permission.
const canPublish = computed(
  () => can('rd.version.publish') && !!item.value && item.value.status === 'READY',
)
const frozen = computed(() => (item.value ? versionRequirementSetFrozen(item.value.status) : true))
const canManageReqs = computed(() => canEdit.value && canViewRequirements.value && !frozen.value)
const statusActions = computed<VersionStatusAction[]>(() =>
  item.value ? availableVersionStatusActions(item.value.status, canChangeStatus.value) : [],
)
const completionPct = computed(() =>
  stats.value ? Math.round(stats.value.completion_rate * 100) : 0,
)

// --- status dialog ---
const statusDialog = ref(false)
const statusSubmitting = ref(false)
const currentAction = ref<VersionStatusAction | null>(null)
const statusReason = ref('')

function openStatusDialog(action: VersionStatusAction): void {
  currentAction.value = action
  statusReason.value = ''
  statusDialog.value = true
}

async function submitStatus(): Promise<void> {
  if (!item.value || !currentAction.value) return
  const action = currentAction.value
  if (action.needsReason && statusReason.value.trim().length < 2) {
    ElMessage.warning('请填写原因（至少 2 个字符）')
    return
  }
  statusSubmitting.value = true
  try {
    await changeVersionStatus(item.value.id, action.target, item.value.revision, statusReason.value.trim() || null)
    ElMessage.success('状态已更新')
    statusDialog.value = false
  } catch {
    // surfaced globally
  } finally {
    statusSubmitting.value = false
    await load()
  }
}

// --- publish dialog ---
const publishDialog = ref(false)
const publishSubmitting = ref(false)
const checkLoading = ref(false)
const releaseNotes = ref('')
const checkCandidatePassed = ref(false)
const checks = ref<PublishCheckItem[]>([])

async function openPublish(): Promise<void> {
  if (!item.value) return
  releaseNotes.value = ''
  checks.value = []
  checkCandidatePassed.value = false
  checkLoading.value = true
  publishDialog.value = true
  // Run the same pre-publish check the server enforces; render it inline.
  try {
    const result = await checkVersionPublish(item.value.id)
    checks.value = result.checks
    checkCandidatePassed.value = result.passed
  } catch (e: unknown) {
    const data = (e as { response?: { data?: { data?: { checks?: PublishCheckItem[] } } } })
      .response?.data?.data
    checks.value = data?.checks ?? []
    checkCandidatePassed.value = false
  } finally {
    checkLoading.value = false
  }
}

async function submitPublish(): Promise<void> {
  if (!item.value) return
  if (!releaseNotes.value.trim()) {
    ElMessage.warning('请填写发布说明')
    return
  }
  publishSubmitting.value = true
  try {
    await publishVersion(item.value.id, releaseNotes.value.trim(), item.value.revision)
    ElMessage.success('版本已发布')
    publishDialog.value = false
  } catch {
    // 409 (未就绪/未完成需求/并发) surfaced globally; reload to refresh state.
  } finally {
    publishSubmitting.value = false
    await load()
  }
}

// --- edit dialog ---
const editDialog = ref(false)
const editSubmitting = ref(false)
const editForm = reactive({ name: '', planned_release_date: null as string | null, description: '' })

function openEdit(): void {
  if (!item.value) return
  Object.assign(editForm, {
    name: item.value.name,
    planned_release_date: item.value.planned_release_date ?? null,
    description: item.value.description ?? '',
  })
  editDialog.value = true
}

async function submitEdit(): Promise<void> {
  if (!item.value) return
  editSubmitting.value = true
  try {
    await updateVersion(item.value.id, {
      name: editForm.name.trim(),
      planned_release_date: editForm.planned_release_date || null,
      description: editForm.description.trim() || null,
      revision: item.value.revision,
    })
    ElMessage.success('版本已更新')
    editDialog.value = false
  } catch {
    // surfaced globally
  } finally {
    editSubmitting.value = false
    await load()
  }
}

// --- add requirement dialog ---
const addDialog = ref(false)
const addSubmitting = ref(false)
const addRequirementId = ref<number | null>(null)

async function submitAdd(): Promise<void> {
  if (!item.value || !addRequirementId.value) {
    ElMessage.warning('请填写需求 ID')
    return
  }
  addSubmitting.value = true
  try {
    // Fetch the requirement's current revision for the optimistic lock.
    const req = await getRequirement(addRequirementId.value)
    await addVersionRequirement(item.value.id, req.id, req.revision, item.value.revision)
    ElMessage.success('需求已加入版本')
    addDialog.value = false
    addRequirementId.value = null
  } catch {
    // 404 / 409 surfaced globally
  } finally {
    addSubmitting.value = false
    await load()
  }
}

// --- move requirement dialog ---
const moveDialog = ref(false)
const moveSubmitting = ref(false)
const moveTarget = reactive({ requirement: null as Requirement | null, target_version_id: null as number | null, reason: '' })

function openMove(req: Requirement): void {
  moveTarget.requirement = req
  moveTarget.target_version_id = null
  moveTarget.reason = ''
  moveDialog.value = true
}

async function submitMove(): Promise<void> {
  if (!moveTarget.requirement || !moveTarget.target_version_id) {
    ElMessage.warning('请填写目标版本 ID')
    return
  }
  if (moveTarget.reason.trim().length < 2) {
    ElMessage.warning('请填写迁移原因（至少 2 个字符）')
    return
  }
  moveSubmitting.value = true
  try {
    const targetVersion = await getVersion(moveTarget.target_version_id)
    await moveVersionRequirement(
      moveTarget.target_version_id,
      moveTarget.requirement.id,
      moveTarget.requirement.revision,
      targetVersion.revision,
      moveTarget.reason.trim(),
    )
    ElMessage.success('需求已迁移')
    moveDialog.value = false
  } catch {
    // surfaced globally
  } finally {
    moveSubmitting.value = false
    await load()
  }
}

async function removeReq(req: Requirement): Promise<void> {
  if (!item.value) return
  await removeVersionRequirement(item.value.id, req.id, req.revision, item.value.revision, null)
  ElMessage.success('需求已移出')
  await load()
}

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    item.value = await getVersion(id)
    const sections = await loadVersionDetailSections(id, can, {
      requirements: listVersionRequirements,
      releases: async (versionId) => (await listReleases({ version_id: versionId })).items,
    })
    requirements.value = sections.requirements?.items ?? []
    stats.value = sections.requirements?.stats ?? null
    releases.value = sections.releases ?? []
  } catch {
    failed.value = true
    item.value = null
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section v-loading="loading" class="page">
    <ErrorState v-if="failed" title="版本加载失败" description="请检查网络或确认版本是否仍可访问。" retry-label="重新加载" @retry="load" />
    <template v-if="item">
      <PageHeader :title="item.name" :eyebrow="item.version_no">
        <template #status>
          <StatusTag :status="item.status" :label="versionStatusLabel[item.status]" :type="versionStatusTagType(item.status)" />
        </template>
        <template v-if="canEdit || canPublish || statusActions.length" #actions>
        <el-button v-if="canEdit" @click="openEdit">编辑</el-button>
        <el-button v-if="canPublish" type="primary" @click="openPublish">发布</el-button>
        <el-button
          v-for="action in statusActions"
          :key="action.target"
          type="primary"
          plain
          @click="openStatusDialog(action)"
        >
          {{ action.label }}
        </el-button>
        </template>
      </PageHeader>

      <SectionCard title="版本概况" description="时间安排与版本说明">
        <el-descriptions :column="isMobile ? 1 : 2">
          <el-descriptions-item label="计划上线">{{ item.planned_release_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="实际上线">{{ formatLocalDateTime(item.released_at) }}</el-descriptions-item>
          <el-descriptions-item label="说明" :span="isMobile ? 1 : 2">
            <div class="multiline">{{ item.description || '-' }}</div>
          </el-descriptions-item>
        </el-descriptions>
      </SectionCard>

      <!-- progress + requirements -->
      <SectionCard v-if="canViewRequirements" title="需求清单" :description="`可见需求 ${stats?.total ?? 0} 项`" class="section">
        <template #actions>
          <el-button v-if="canManageReqs" size="small" type="primary" @click="addDialog = true">
            添加需求
          </el-button>
        </template>
        <div v-if="stats" class="progress">
          <el-progress :percentage="completionPct" :stroke-width="14" />
          <span class="progress-text">完成 {{ stats.completed }} / {{ stats.total }}</span>
        </div>
        <el-table v-if="requirements.length && !isMobile" :data="requirements" row-key="id">
          <el-table-column prop="requirement_no" label="编号" width="170" />
          <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
          <el-table-column label="状态" width="110">
            <template #default="s">
              <StatusTag
                :status="s.row.status"
                :label="requirementStatusLabel[s.row.status]"
                :type="requirementStatusTagType(s.row.status)"
              />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180">
            <template #default="s">
              <el-link type="primary" @click="router.push('/requirements/' + s.row.id)">查看</el-link>
              <template v-if="canManageReqs">
                <el-link type="warning" style="margin-left: 10px" @click="openMove(s.row)">迁移</el-link>
                <el-link type="danger" style="margin-left: 10px" @click="removeReq(s.row)">移出</el-link>
              </template>
            </template>
          </el-table-column>
        </el-table>
        <div v-else-if="requirements.length" class="req-cards">
          <article v-for="req in requirements" :key="req.id" class="req-card">
            <div class="req-card-top"><span class="mono">{{ req.requirement_no }}</span><StatusTag :status="req.status" :label="requirementStatusLabel[req.status]" size="sm" /></div>
            <div class="req-card-title">{{ req.title }}</div>
            <div class="req-card-actions">
              <el-button link type="primary" @click="router.push('/requirements/' + req.id)">查看</el-button>
              <template v-if="canManageReqs">
                <el-button link type="warning" @click="openMove(req)">迁移</el-button>
                <el-button link type="danger" @click="removeReq(req)">移出</el-button>
              </template>
            </div>
          </article>
        </div>
        <EmptyState v-else description="暂无可见需求" compact />
        <p v-if="frozen" class="frozen-tip">版本处于 {{ versionStatusLabel[item.status] }}，需求清单已冻结。</p>
      </SectionCard>

      <!-- release history -->
      <SectionCard v-if="canViewReleases" title="发布历史" class="section">
        <ul v-if="releases.length" class="releases">
          <li v-for="r in releases" :key="r.id">
            <span class="release-time">{{ formatLocalDateTime(r.released_at) }}</span>
            <StatusTag :status="r.result" :label="r.result === 'SUCCESS' ? '成功' : r.result" size="sm" />
            <span class="release-notes">{{ r.release_notes }}</span>
          </li>
        </ul>
        <EmptyState v-else description="尚无发布记录" compact />
      </SectionCard>
    </template>

    <!-- publish dialog -->
    <el-dialog v-model="publishDialog" title="发布版本" width="min(520px, 92vw)" destroy-on-close>
      <p class="publish-tip">发布后版本将进入「已发布」，其已完成需求与关联反馈会自动置为「已上线」。此操作不可撤销。</p>
      <div v-loading="checkLoading" class="checks">
        <div class="checks-title">发布前检查</div>
        <ul>
          <li v-for="c in checks" :key="c.type">
            <el-tag :type="c.passed ? 'success' : 'danger'" size="small" effect="light">
              {{ c.passed ? '通过' : '未通过' }}
            </el-tag>
            <span class="check-msg">{{ c.message }}</span>
            <ul v-if="c.blocking_requirements && c.blocking_requirements.length" class="blocking">
              <li v-for="b in c.blocking_requirements" :key="b.id">
                {{ b.requirement_no }}（{{ b.status }}）
              </li>
            </ul>
          </li>
        </ul>
      </div>
      <el-form label-position="top">
        <el-form-item label="发布说明" required>
          <el-input v-model="releaseNotes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="publishDialog = false">取消</el-button>
        <el-button
          type="success"
          :loading="publishSubmitting"
          :disabled="checkLoading || !checkCandidatePassed"
          @click="submitPublish"
        >
          确认发布
        </el-button>
      </template>
    </el-dialog>

    <!-- status dialog -->
    <el-dialog v-model="statusDialog" :title="currentAction?.label ?? '状态变更'" width="min(480px, 92vw)" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="原因" :required="currentAction?.needsReason">
          <el-input v-model="statusReason" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="statusDialog = false">取消</el-button>
        <el-button type="primary" :loading="statusSubmitting" @click="submitStatus">确定</el-button>
      </template>
    </el-dialog>

    <!-- edit dialog -->
    <el-dialog v-model="editDialog" title="编辑版本" width="min(520px, 92vw)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="submitEdit">
        <el-form-item label="版本名称">
          <el-input v-model="editForm.name" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="计划上线日期">
          <el-date-picker v-model="editForm.planned_release_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="editForm.description" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- add requirement dialog -->
    <el-dialog v-model="addDialog" title="添加需求" width="min(420px, 92vw)" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="需求 ID" required>
          <el-input-number v-model="addRequirementId" :min="1" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialog = false">取消</el-button>
        <el-button type="primary" :loading="addSubmitting" @click="submitAdd">添加</el-button>
      </template>
    </el-dialog>

    <!-- move requirement dialog -->
    <el-dialog v-model="moveDialog" title="迁移需求到其他版本" width="min(480px, 92vw)" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="目标版本 ID" required>
          <el-input-number v-model="moveTarget.target_version_id" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="迁移原因" required>
          <el-input v-model="moveTarget.reason" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="moveDialog = false">取消</el-button>
        <el-button type="primary" :loading="moveSubmitting" @click="submitMove">确定</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.multiline { white-space: pre-wrap; overflow-wrap: anywhere; }
.section { margin-top: var(--if-space-4); }
.section :deep(.el-table) { width: 100%; }
.progress { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.progress .el-progress { flex: 1; }
.progress-text { color: var(--if-text-2); font-size: 13px; white-space: nowrap; }
.frozen-tip { margin: 14px 0 0; padding: 10px 12px; border-radius: var(--if-radius-sm); background: var(--if-warning-bg); color: var(--if-warning-fg); font-size: 12px; }
.req-cards { display: grid; gap: 8px; }
.req-card { min-width: 0; padding: 12px; border: 1px solid var(--if-border); border-radius: var(--if-radius-sm); }
.req-card-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.req-card-title { margin: 8px 0; font-size: 14px; font-weight: 650; overflow-wrap: anywhere; }
.req-card-actions { display: flex; flex-wrap: wrap; gap: 12px; border-top: 1px solid var(--if-border); padding-top: 8px; }
.req-card-actions .el-button { margin: 0; }
.publish-tip { margin: 0 0 16px; padding: 12px; border-radius: var(--if-radius-sm); background: var(--if-brand-50); color: var(--if-text-2); font-size: 13px; line-height: 1.5; }
.checks { min-height: 70px; margin-bottom: 16px; padding: 12px; border: 1px solid var(--if-border); border-radius: var(--if-radius-sm); }
.checks-title { font-weight: 650; margin-bottom: 8px; }
.checks ul { list-style: none; margin: 0; padding: 0; }
.checks > ul > li { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; padding: 6px 0; }
.check-msg { color: var(--if-text-2); font-size: 13px; }
.blocking { width: 100%; margin: 2px 0 0 24px; color: var(--if-danger-fg); font-size: 12px; }
.releases { list-style: none; margin: 0; padding: 0; }
.releases li { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--if-border); }
.releases li:last-child { border-bottom: 0; }
.release-time { color: var(--if-text-3); font-size: 12px; white-space: nowrap; }
.release-notes { color: var(--if-text-2); font-size: 13px; overflow-wrap: anywhere; }
@media (max-width: 767px) { .progress { flex-wrap: wrap; } .progress .el-progress { min-width: 100%; } }
</style>
