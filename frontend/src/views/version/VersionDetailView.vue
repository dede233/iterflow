<script setup lang="ts">
import VersionReleaseBatches from "@/components/VersionReleaseBatches.vue"
import BusinessSystemAttribution from '@/components/BusinessSystemAttribution.vue'
import RecentEntityActivity from '@/components/RecentEntityActivity.vue'
import BusinessSystemSelect from '@/components/BusinessSystemSelect.vue'
import BatchActionsDialog from '@/components/BatchActionsDialog.vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  changeVersionStatus,
  checkVersionPublish,
  getVersion,
  listVersionRequirements,
  moveVersionRequirement,
  publishVersion,
  removeVersionRequirement,
  updateVersion,
} from '@/api/versions'
import ReleaseVersionDrawer from '@/components/ReleaseVersionDrawer.vue'
import { listReleases } from '@/api/releases'
import { getRequirement } from '@/api/requirements'
import BulkRequirementPicker from '@/components/BulkRequirementPicker.vue'
import ScopedObjectSelector from '@/components/ScopedObjectSelector.vue'
import ScopedRelationLink from '@/components/ScopedRelationLink.vue'
import RequirementSummaryDialog from '@/components/RequirementSummaryDialog.vue'
import { filterVersionWorklist, visibleWorklistStats } from '@/utils/versionWorklist'
import { useDetailNavigation } from '@/composables/useDetailNavigation'
import { usePermission } from '@/composables/usePermission'
import { useEditingPresence } from '@/composables/useEditingPresence'
import { useRevisionConflict } from '@/composables/useRevisionConflict'
import { loadVersionDetailSections } from '@/security/detailAuthorization'
import StatusTag from '@/components/StatusTag.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import RevisionConflictDialog from '@/components/RevisionConflictDialog.vue'
import { useResponsive } from '@/composables/useResponsive'
import { formatLocalDateTime } from '@/utils/dates'
import { requirementConflictSummary, versionConflictSummary } from '@/utils/revisionSummaries'
import {
  availableVersionStatusActions,
  versionRequirementSetFrozen,
  versionStatusLabel,
  versionStatusTagType,
  type VersionStatusAction,
} from '@/constants/version'
import { REQUIREMENT_PRIORITIES, REQUIREMENT_STATUSES, requirementStatusLabel, requirementStatusTagType } from '@/constants/requirement'
import type {
  PublishCheckItem,
  ReleaseItem,
  Requirement,
  VersionItem,
  VersionStats,
} from '@/types/domain'

const props = defineProps<{ embedded?: boolean; embeddedId?: number; returnTo?: string }>()
const emit = defineEmits<{ updated: []; close: []; 'open-release': [id: number] }>()
const route = useRoute()
const router = useRouter()
const { backTo, related } = useDetailNavigation('/versions', () => props.returnTo)
const { can } = usePermission()
const { isMobile } = useResponsive()
const id = Number(props.embedded ? props.embeddedId : route.params.id)
const { start: startPresence, stop: stopPresence, existingEditor } = useEditingPresence('VERSION', id)
const conflict = useRevisionConflict()
const summaryRequirementId = ref<number | null>(null)
watch(() => [route.params.id, props.embeddedId], () => { summaryRequirementId.value = null })

async function showVersionConflict(error: unknown, revision: number, onReload?: (latest: VersionItem) => void | Promise<void>): Promise<void> {
  await conflict.show(error, revision, {
    entityLabel: '版本',
    getLatest: () => getVersion(id),
    summarize: versionConflictSummary,
    apply: async (latest) => {
      item.value = latest
      await onReload?.(latest)
    },
  })
}

async function showRelationConflict(
  error: unknown,
  versionRevision: number,
  requirementRevision: number,
  requirementId: number,
  versionId: number,
): Promise<void> {
  await conflict.show(error, `版本 ${versionRevision} / 需求 ${requirementRevision}`, {
    entityLabel: '版本与需求关联',
    getLatest: async () => {
      const [version, requirement, currentVersion, section] = await Promise.all([
        getVersion(versionId),
        getRequirement(requirementId),
        getVersion(id),
        listVersionRequirements(id),
      ])
      return { version, requirement, currentVersion, section }
    },
    summarize: ({ version, requirement }) => [
      { label: '版本当前 revision', value: String(version.revision) },
      ...versionConflictSummary(version).map((row) => ({ label: `版本 · ${row.label}`, value: row.value })),
      { label: '需求当前 revision', value: String(requirement.revision) },
      ...requirementConflictSummary(requirement).map((row) => ({ label: `需求 · ${row.label}`, value: row.value })),
    ],
    apply: ({ currentVersion, section }) => {
      item.value = currentVersion
      requirements.value = section.items
      stats.value = section.stats
    },
  })
}

const item = ref<VersionItem | null>(null)
const requirements = ref<Requirement[]>([])
const stats = ref<VersionStats | null>(null)
const worklistFilters = reactive({ keyword: '', status: '', priority: '' })
const filteredRequirements = computed(() => filterVersionWorklist(requirements.value, worklistFilters))
const visibleStats = computed(() => visibleWorklistStats(requirements.value))
function resetWorklist(): void { worklistFilters.keyword = ''; worklistFilters.status = ''; worklistFilters.priority = '' }
const releases = ref<ReleaseItem[]>([])
const releaseDrawer = ref(false)
const activeReleaseId = ref<number | null>(null)
function openRelease(releaseId: number): void {
  if (!canViewReleases.value) return
  if (props.embedded) emit('open-release', releaseId)
  else { activeReleaseId.value = releaseId; releaseDrawer.value = true }
}
const loading = ref(false)
const activityRefresh = ref(0)
const failed = ref(false)

const canEdit = computed(() => can('rd.version.edit'))
const canChangeStatus = computed(() => can('rd.version.status'))
const canViewRequirements = computed(() => can('rd.requirement.view'))
const canViewReleases = computed(() => can('rd.release.view'))
// Every active version can explain its blockers; only passing checks enable publishing.
const targetPlanActive = ref(false)
const canPublish = computed(
  () => can('rd.version.publish') && !!item.value && !['RELEASED', 'CANCELED'].includes(item.value.status),
)
const frozen = computed(() => (item.value ? (item.value.release_frozen || versionRequirementSetFrozen(item.value.status)) : true))
const canManageReqs = computed(() => canEdit.value && canViewRequirements.value && !frozen.value)
const statusActions = computed<VersionStatusAction[]>(() =>
  item.value && !item.value.release_frozen ? availableVersionStatusActions(item.value.status, canChangeStatus.value) : [],
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
  if (!item.value || !currentAction.value || statusSubmitting.value) return
  const action = currentAction.value
  if (action.needsReason && statusReason.value.trim().length < 2) {
    ElMessage.warning('请填写原因（至少 2 个字符）')
    return
  }
  statusSubmitting.value = true
  try {
    await changeVersionStatus(item.value.id, action.target, item.value.revision, statusReason.value.trim() || null)
    emit('updated')
    ElMessage.success('状态已更新')
    statusDialog.value = false
    await load()
  } catch (error) {
    await showVersionConflict(error, item.value.revision, () => { statusDialog.value = false })
  } finally {
    statusSubmitting.value = false
  }
}

// --- publish dialog ---
const publishDialog = ref(false)
const publishSubmitting = ref(false)
const checkLoading = ref(false)
const legacyReason = ref('')
const releaseNotes = ref('')
const checkCandidatePassed = ref(false)
const checks = ref<PublishCheckItem[]>([])
let checkSequence = 0
onBeforeUnmount(() => { checkSequence++; conflict.close() })
watch(publishDialog, open => { if (!open) { checkSequence++; checks.value = []; checkLoading.value = false; checkCandidatePassed.value = false } }, { flush: 'sync' })

async function openPublish(): Promise<void> {
  if (!item.value || !canPublish.value || checkLoading.value || publishSubmitting.value) return
  releaseNotes.value = ''; legacyReason.value = ''
  checks.value = []
  checkCandidatePassed.value = false
  checkLoading.value = true
  publishDialog.value = true
  const sequence = ++checkSequence
  // Run the same pre-publish check the server enforces; render it inline.
  try {
    const result = await checkVersionPublish(item.value.id)
    if (sequence !== checkSequence) return
    checks.value = result.checks
    checkCandidatePassed.value = result.passed
  } catch (e: unknown) {
    if (sequence !== checkSequence) return
    const data = (e as { response?: { data?: { data?: { checks?: PublishCheckItem[] } } } })
      .response?.data?.data
    checks.value = data?.checks ?? []
    checkCandidatePassed.value = false
  } finally {
    if (sequence === checkSequence) checkLoading.value = false
  }
}

async function submitPublish(): Promise<void> {
  if (!item.value || !canPublish.value || publishSubmitting.value || checkLoading.value || !checkCandidatePassed.value) return
  if (!releaseNotes.value.trim() || legacyReason.value.trim().length < 2) {
    ElMessage.warning('请填写发布说明和传统发布原因（至少 2 个字符）')
    return
  }
  publishSubmitting.value = true
  try {
    await publishVersion(item.value.id, releaseNotes.value.trim(), item.value.revision, legacyReason.value.trim())
    emit('updated')
    ElMessage.success('版本已发布')
    publishDialog.value = false
    await load()
  } catch (error) {
    await showVersionConflict(error, item.value.revision, () => { publishDialog.value = false })
  } finally {
    publishSubmitting.value = false
  }
}

// --- edit dialog ---
const editDialog = ref(false)
const editSubmitting = ref(false)
const editForm = reactive({ system_id: null as number | null, name: '', planned_release_date: null as string | null, description: '' })

function openEdit(): void {
  if (!item.value || !canEdit.value) return
  fillEditForm(item.value)
  editDialog.value = true
  void startPresence()
}

function fillEditForm(latest: VersionItem): void {
  Object.assign(editForm, {
    system_id: latest.system_id,
    name: latest.name,
    planned_release_date: latest.planned_release_date ?? null,
    description: latest.description ?? '',
  })
}

watch(editDialog, (open) => {
  if (!open) void stopPresence()
})

async function submitEdit(): Promise<void> {
  if (!item.value) return
  editSubmitting.value = true
  try {
    await updateVersion(item.value.id, {
      ...(editForm.system_id !== item.value.system_id ? { system_id: editForm.system_id } : {}),
      name: editForm.name.trim(),
      planned_release_date: editForm.planned_release_date || null,
      ...(!item.value.release_frozen ? { description: editForm.description.trim() || null } : {}),
      revision: item.value.revision,
    })
    emit('updated')
    ElMessage.success('版本已更新')
    editDialog.value = false
    await load()
  } catch (error) {
    await showVersionConflict(error, item.value.revision, fillEditForm)
  } finally {
    editSubmitting.value = false
  }
}

// --- add requirement dialog ---
const addDialog = ref(false)
async function onBulkAdded() { addDialog.value = false; emit('updated'); await load() }

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
  let targetRevision = 0
  let requirementRevision = moveTarget.requirement.revision
  try {
    const latestRequirement = await getRequirement(moveTarget.requirement.id)
    requirementRevision = latestRequirement.revision
    if (latestRequirement.current_version_id !== id) {
      ElMessage.warning('需求所属版本已变化，请重新加载清单后再迁移')
      moveDialog.value = false
      await load()
      return
    }
    const targetVersion = await getVersion(moveTarget.target_version_id)
    targetRevision = targetVersion.revision
    await moveVersionRequirement(
      moveTarget.target_version_id,
      moveTarget.requirement.id,
      latestRequirement.revision,
      targetVersion.revision,
      moveTarget.reason.trim(),
    )
    emit('updated')
    ElMessage.success('需求已迁移')
    moveDialog.value = false
    await load()
  } catch (error) {
    if (moveTarget.requirement && moveTarget.target_version_id) {
      await showRelationConflict(error, targetRevision, requirementRevision, moveTarget.requirement.id, moveTarget.target_version_id)
    }
  } finally {
    moveSubmitting.value = false
  }
}

async function removeReq(req: Requirement): Promise<void> {
  if (!item.value) return
  try {
    await removeVersionRequirement(item.value.id, req.id, req.revision, item.value.revision, null)
    emit('updated')
    ElMessage.success('需求已移出')
    await load()
  } catch (error) {
    await showRelationConflict(error, item.value.revision, req.revision, req.id, item.value.id)
  }
}

async function load(): Promise<void> {
  activityRefresh.value++
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
        <template #actions>
        <el-button v-if="embedded" link @click="emit('close')">关闭详情</el-button>
        <RouterLink v-else class="back-link" :to="backTo">返回列表</RouterLink>
        <el-button v-if="canEdit" @click="openEdit">编辑</el-button>
        <el-button v-if="canPublish && !targetPlanActive && !item.release_frozen" type="primary" @click="openPublish">{{ item.status === 'READY' ? '传统单次发布' : '发布检查' }}</el-button>
        <el-button
          v-for="action in statusActions"
          :key="action.target"
          type="default"
          plain
          @click="openStatusDialog(action)"
        >
          {{ action.label }}
        </el-button>
        </template>
      </PageHeader>
      <BusinessSystemAttribution :system-id="item.system_id" :system-name="item.system_name" />

      <el-alert v-if="!item.system_id && !frozen" title="此历史版本未指定业务系统，请先补齐需求系统，再编辑版本选择同一系统。" type="warning" :closable="false" />
      <SectionCard title="版本概况" description="进度由关联需求自动汇总；开发和验收在需求中完成。">
        <el-descriptions :column="isMobile ? 1 : 2">
          <el-descriptions-item label="计划上线">{{ item.planned_release_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="实际上线">{{ formatLocalDateTime(item.released_at) }}</el-descriptions-item>
          <el-descriptions-item label="说明" :span="isMobile ? 1 : 2">
            <div class="multiline">{{ item.description || '-' }}</div>
          </el-descriptions-item>
        </el-descriptions>
      </SectionCard>

      <VersionReleaseBatches :version="item" @updated="load" @plan-state="targetPlanActive = $event" />

      <RecentEntityActivity kind="version" :id="item.id" :revision="item.revision" :refresh-key="activityRefresh" />

      <!-- progress + requirements -->
      <SectionCard v-if="canViewRequirements" title="需求清单" :description="`可见需求 ${stats?.total ?? 0} 项`" class="section">
        <template #actions>
          <BatchActionsDialog v-if="!frozen" kind="requirements" scope="version-list" :version-id="item.id" :version-revision="item.revision" :rows="filteredRequirements" @updated="load" />
          <el-button v-if="canManageReqs" size="small" type="primary" @click="addDialog = true">
            添加需求
          </el-button>
        </template>
        <div v-if="stats" class="progress">
          <el-progress :percentage="completionPct" :stroke-width="14" />
          <span class="progress-text">可见需求进度 {{ stats.completed }} / {{ stats.total }}</span>
        </div>
        <p class="scope-tip">仅统计当前账号可见需求；发布准备以服务端发布检查为准。</p>
        <div class="worklist-summary" aria-label="可见需求状态分布">
          <span>可见待完成 {{ visibleStats.pending }} / {{ visibleStats.total }}</span>
          <el-button v-for="(count, status) in visibleStats.byStatus" :key="status" size="small" :aria-pressed="worklistFilters.status === status" :type="worklistFilters.status === status ? 'primary' : 'default'" @click="worklistFilters.status = String(status)">{{ requirementStatusLabel[status] || status }} {{ count }}</el-button>
        </div>
        <el-form class="worklist-filters" label-position="top" @submit.prevent>
          <el-form-item label="清单关键词"><el-input v-model="worklistFilters.keyword" placeholder="筛选可见编号或标题" clearable :maxlength="200" /></el-form-item>
          <el-form-item label="清单状态"><el-select v-model="worklistFilters.status" clearable placeholder="全部可见状态"><el-option v-for="option in REQUIREMENT_STATUSES" :key="option.value" :value="option.value" :label="option.label" /></el-select></el-form-item>
          <el-form-item label="清单优先级"><el-select v-model="worklistFilters.priority" clearable placeholder="全部优先级"><el-option v-for="option in REQUIREMENT_PRIORITIES" :key="option.value" :value="option.value" :label="option.label" /></el-select></el-form-item>
          <el-button @click="resetWorklist">重置清单</el-button>
        </el-form>
        <p class="scope-tip">当前筛选 {{ filteredRequirements.length }} / {{ visibleStats.total }} 项可见需求</p>
        <el-table v-if="!isMobile" :data="filteredRequirements" row-key="id">
          <el-table-column prop="requirement_no" label="编号" width="170" />
          <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
          <el-table-column prop="priority" label="优先级" width="90" />
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
              <el-link type="primary" @click="summaryRequirementId = s.row.id">查看</el-link>
              <template v-if="canManageReqs">
                <el-link type="warning" style="margin-left: 10px" @click="openMove(s.row)">迁移</el-link>
                <el-link type="danger" style="margin-left: 10px" @click="removeReq(s.row)">移出</el-link>
              </template>
            </template>
          </el-table-column>
        </el-table>
        <div v-else-if="filteredRequirements.length" class="req-cards">
          <article v-for="req in filteredRequirements" :key="req.id" class="req-card">
            <div class="req-card-top"><span class="mono">{{ req.requirement_no }}</span><StatusTag :status="req.status" :label="requirementStatusLabel[req.status]" size="sm" /></div>
            <div class="req-card-title">{{ req.title }}</div>
            <p>优先级 {{ req.priority }}</p>
            <div class="req-card-actions">
              <el-button link type="primary" @click="summaryRequirementId = req.id">查看</el-button>
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
            <el-button link type="primary" @click="openRelease(r.id)">查看发布详情</el-button>
          </li>
        </ul>
        <EmptyState v-else description="尚无发布记录" compact />
      </SectionCard>
    </template>

    <RequirementSummaryDialog :id="summaryRequirementId" :return-to="backTo" @close="summaryRequirementId = null" />
    <ReleaseVersionDrawer v-if="!embedded" v-model="releaseDrawer" kind="release" :id="activeReleaseId" :return-to="backTo" @updated="load" />

    <!-- publish dialog -->
    <el-dialog v-model="publishDialog" title="传统单次发布" width="min(520px, 92vw)" destroy-on-close>
      <p>需按小程序分别记录时，请关闭此窗口，在「发布目标与批次」创建首次计划。已有首次计划不能通过传统路径发布。</p>
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
                {{ b.requirement_no }}（{{ requirementStatusLabel[b.status] || b.status }}）
                <ScopedRelationLink v-if="publishDialog" kind="requirement" :id="b.id" :return-to="backTo" :parent-identity="`${id}:publish:${checkSequence}`" fallback="无法查看详情" link-label="查看需求" />
              </li>
            </ul>
          </li>
        </ul>
      </div>
      <el-form label-position="top">
        <el-form-item label="传统单次发布原因" required><el-input v-model="legacyReason" type="textarea" maxlength="500" placeholder="说明本次无需记录具体发布目标的原因" /></el-form-item>
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

    <RevisionConflictDialog
      :visible="conflict.visible"
      :loading="conflict.loading"
      :entity-label="conflict.entityLabel"
      :submitted-revision="conflict.submittedRevision"
      :metadata="conflict.metadata"
      :summary="conflict.summary"
      :read-error="conflict.readError"
      @close="conflict.close"
      @reload="conflict.reload"
    />

    <!-- status dialog -->
    <el-dialog v-model="statusDialog" :title="currentAction?.label ?? '状态变更'" width="min(480px, 92vw)" destroy-on-close>
      <el-form label-position="top">
        <el-form-item v-if="currentAction?.needsReason" label="原因" required>
          <el-input v-model="statusReason" type="textarea" :rows="3" />
        </el-form-item>
        <p v-if="currentAction && !currentAction.needsReason">
          确认将版本状态改为「{{ versionStatusLabel[currentAction.target] }}」？
        </p>
      </el-form>
      <template #footer>
        <el-button @click="statusDialog = false">取消</el-button>
        <el-button type="primary" :loading="statusSubmitting" @click="submitStatus">确定</el-button>
      </template>
    </el-dialog>

    <!-- edit dialog -->
    <el-dialog v-model="editDialog" title="编辑版本" width="min(520px, 92vw)" destroy-on-close>
      <el-alert v-if="existingEditor" type="warning" :closable="false" show-icon class="presence-alert">
        <template #title>{{ existingEditor.display_name }} 正在编辑此版本</template>
        你仍可继续编辑；如数据已变化，保存时会通过 revision 冲突保护避免静默覆盖。
      </el-alert>
      <el-form label-position="top" @submit.prevent="submitEdit">
        <el-form-item label="业务系统"><BusinessSystemSelect v-model="editForm.system_id" :current-name="item?.system_name" :clearable="false" :disabled="frozen" /></el-form-item>
        <el-form-item label="版本名称">
          <el-input v-model="editForm.name" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="计划上线日期">
          <el-date-picker v-model="editForm.planned_release_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="editForm.description" :disabled="!!item?.release_frozen" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- add requirement dialog -->
    <el-dialog v-model="addDialog" title="批量添加需求" width="min(780px, 94vw)" destroy-on-close append-to-body :close-on-click-modal="false">
      <BulkRequirementPicker v-if="addDialog && item" :version-id="item.id" :revision="item.revision" :system-id="item.system_id" @updated="onBulkAdded" @cancel="addDialog = false" />
    </el-dialog>

    <!-- move requirement dialog -->
    <el-dialog v-model="moveDialog" title="迁移需求到其他版本" width="min(480px, 92vw)" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="目标版本" required>
          <ScopedObjectSelector v-model="moveTarget.target_version_id" kind="version" :allowed="can('rd.version.view')" :active="moveDialog" :disabled="moveSubmitting" :exclude-id="id" :system-id="moveTarget.requirement?.system_id" />
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
.scope-tip { color: var(--if-text-2); font-size: 13px; }
.worklist-summary { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
.worklist-summary :deep(.el-button + .el-button) { margin-left: 0; }
.worklist-filters { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr) auto; gap: 12px; align-items: center; }
.worklist-filters :deep(.el-form-item) { min-width: 0; margin-bottom: 0; }
.worklist-filters :deep(.el-select) { width: 100%; }
@media (max-width: 767px) { .worklist-filters { grid-template-columns: minmax(0, 1fr); } }

.back-link { color: var(--if-brand-500); align-self: center; }
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
.presence-alert { min-width: 0; margin-bottom: var(--if-space-4); overflow-wrap: anywhere; }
.presence-alert :deep(.el-alert__content), .presence-alert :deep(.el-alert__title) { min-width: 0; overflow-wrap: anywhere; }
@media (max-width: 767px) { .progress { flex-wrap: wrap; } .progress .el-progress { min-width: 100%; } }
</style>
