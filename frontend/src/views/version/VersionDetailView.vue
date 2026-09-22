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
import StatusTag from '@/components/StatusTag.vue'
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
const id = Number(route.params.id)

const item = ref<VersionItem | null>(null)
const requirements = ref<Requirement[]>([])
const stats = ref<VersionStats | null>(null)
const releases = ref<ReleaseItem[]>([])
const loading = ref(false)

const canEdit = computed(() => can('rd.version.edit'))
const canChangeStatus = computed(() => can('rd.version.status'))
// Publish entry: only for a READY version and only with the publish permission.
const canPublish = computed(
  () => can('rd.version.publish') && !!item.value && item.value.status === 'READY',
)
const frozen = computed(() => (item.value ? versionRequirementSetFrozen(item.value.status) : true))
const canManageReqs = computed(() => canEdit.value && !frozen.value)
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
const releaseNotes = ref('')
const checkCandidatePassed = ref(false)
const checks = ref<PublishCheckItem[]>([])

async function openPublish(): Promise<void> {
  if (!item.value) return
  releaseNotes.value = ''
  checks.value = []
  checkCandidatePassed.value = false
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
    await addVersionRequirement(item.value.id, req.id, req.revision)
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
    await moveVersionRequirement(
      moveTarget.target_version_id,
      moveTarget.requirement.id,
      moveTarget.requirement.revision,
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
  await removeVersionRequirement(item.value.id, req.id, req.revision, null)
  ElMessage.success('需求已移出')
  await load()
}

async function load(): Promise<void> {
  loading.value = true
  try {
    item.value = await getVersion(id)
    const view = await listVersionRequirements(id)
    requirements.value = view.items
    stats.value = view.stats
    releases.value = (await listReleases({ version_id: id })).items
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section v-loading="loading" class="page">
    <template v-if="item">
      <div class="head">
        <div>
          <div class="no">{{ item.version_no }}</div>
          <h1 class="page-title">{{ item.name }}</h1>
        </div>
        <StatusTag
          :status="item.status"
          :label="versionStatusLabel[item.status]"
          :type="versionStatusTagType(item.status)"
        />
      </div>

      <div v-if="canEdit || canPublish || statusActions.length" class="toolbar">
        <el-button v-if="canEdit" @click="openEdit">编辑</el-button>
        <el-button v-if="canPublish" type="success" @click="openPublish">发布</el-button>
        <el-button
          v-for="action in statusActions"
          :key="action.target"
          type="primary"
          plain
          @click="openStatusDialog(action)"
        >
          {{ action.label }}
        </el-button>
      </div>

      <el-card shadow="never">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="计划上线">{{ item.planned_release_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="实际上线">{{ item.released_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="说明">
            <div class="multiline">{{ item.description || '-' }}</div>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- progress + requirements -->
      <el-card shadow="never" class="section">
        <div class="section-head">
          <span class="section-title">需求清单（{{ stats?.total ?? 0 }}）</span>
          <el-button v-if="canManageReqs" size="small" type="primary" @click="addDialog = true">
            添加需求
          </el-button>
        </div>
        <div v-if="stats" class="progress">
          <el-progress :percentage="completionPct" :stroke-width="14" />
          <span class="progress-text">完成 {{ stats.completed }} / {{ stats.total }}</span>
        </div>
        <el-table v-if="requirements.length" :data="requirements" row-key="id">
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
        <el-empty v-else :image-size="60" description="版本内暂无需求" />
        <p v-if="frozen" class="frozen-tip">版本处于 {{ versionStatusLabel[item.status] }}，需求清单已冻结。</p>
      </el-card>

      <!-- release history -->
      <el-card shadow="never" class="section">
        <div class="section-title">发布历史</div>
        <ul v-if="releases.length" class="releases">
          <li v-for="r in releases" :key="r.id">
            <span class="release-time">{{ r.released_at }}</span>
            <el-tag size="small" type="success" effect="light">{{ r.result }}</el-tag>
            <span class="release-notes">{{ r.release_notes }}</span>
          </li>
        </ul>
        <el-empty v-else :image-size="60" description="尚无发布记录" />
      </el-card>
    </template>

    <!-- publish dialog -->
    <el-dialog v-model="publishDialog" title="发布版本" width="min(520px, 92vw)" destroy-on-close>
      <p class="publish-tip">发布后版本将进入「已发布」，其已完成需求与关联反馈会自动置为「已上线」。此操作不可撤销。</p>
      <div class="checks">
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
          :disabled="!checkCandidatePassed"
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
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
.no { font-size: 12px; color: #94a3b8; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.multiline { white-space: pre-wrap; }
.section { margin-top: 16px; }
.section-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.section-title { font-weight: 600; }
.progress { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.progress .el-progress { flex: 1; }
.progress-text { color: #64748b; font-size: 13px; white-space: nowrap; }
.frozen-tip { margin: 10px 0 0; color: #b45309; font-size: 13px; }
.publish-tip { margin: 0 0 12px; color: #64748b; font-size: 13px; line-height: 1.5; }
.checks { margin-bottom: 12px; }
.checks-title { font-weight: 600; margin-bottom: 6px; }
.checks ul { list-style: none; margin: 0; padding: 0; }
.checks > ul > li { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; padding: 4px 0; }
.check-msg { color: #475569; font-size: 13px; }
.blocking { width: 100%; margin: 2px 0 0 24px; color: #b91c1c; font-size: 12px; }
.releases { list-style: none; margin: 0; padding: 0; }
.releases li { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid #f1f5f9; }
.release-time { color: #94a3b8; font-size: 12px; white-space: nowrap; }
.release-notes { color: #475569; }
</style>
