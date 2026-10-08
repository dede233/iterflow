<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { getApiDocumentation } from '@/api/documentation'
import { documentedOperations, responseDescription, schemaType } from '@/utils/apiDocumentation'
import type { OpenApiDocument } from '@/utils/apiDocumentation'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import ErrorState from '@/components/ui/ErrorState.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import ApiSchemaView from '@/components/ApiSchemaView.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const document = ref<OpenApiDocument | null>(null)
const loading = ref(false)
const failed = ref(false)
const keyword = ref('')
const group = ref('')
const expanded = ref<string[]>([])
let sequence = 0
const operations = computed(() => document.value ? documentedOperations(document.value) : [])
const groups = computed(() => [...new Set(operations.value.map(item => item.group))])
const filtered = computed(() => operations.value.filter(item => (!group.value || item.group === group.value) && `${item.method} ${item.path} ${item.summary ?? ''} ${item.description ?? ''} ${item.group}`.toLowerCase().includes(keyword.value.trim().toLowerCase())))

async function load(): Promise<void> {
  const request = ++sequence
  loading.value = true
  failed.value = false
  document.value = null
  if (!auth.canViewApiDocs) { failed.value = true; loading.value = false; return }
  try {
    const result = await getApiDocumentation()
    if (request === sequence) document.value = result
  } catch {
    if (request === sequence) failed.value = true
  } finally {
    if (request === sequence) loading.value = false
  }
}

function download(): void {
  if (!document.value) return
  const url = URL.createObjectURL(new Blob([JSON.stringify(document.value, null, 2)], { type: 'application/json' }))
  const link = window.document.createElement('a')
  link.href = url
  link.download = 'iterflow-openapi.json'
  link.click()
  URL.revokeObjectURL(url)
}

onMounted(load)
watch(() => auth.canViewApiDocs, allowed => {
  if (!allowed) { sequence++; document.value = null; failed.value = true; loading.value = false }
})
onBeforeUnmount(() => { sequence++; document.value = null })
</script>

<template>
  <section v-loading="loading" class="page documentation-page">
    <PageHeader title="接口文档" description="查看接口路径、请求参数和响应结构。" eyebrow="开发支持">
      <template #actions><el-button :disabled="!document" @click="download">下载 OpenAPI</el-button></template>
    </PageHeader>
    <ErrorState v-if="failed" title="接口文档不可访问" description="请确认账号仍具有启用的超级管理员或研发负责人角色，或稍后重试。" retry-label="重新加载" @retry="load" />
    <template v-else-if="document">
      <SectionCard title="访问与认证" :description="`API ${document.info.version} · 共 ${operations.length} 个接口`">
        <p class="guide">仅超级管理员和研发负责人可以查看此文档。业务接口仍按各自权限和数据范围校验。</p>
        <p class="guide">需要登录的接口使用请求头 <code>Authorization: Bearer &lt;Access Token&gt;</code>。刷新凭证请使用账号认证接口。</p>
      </SectionCard>
      <SectionCard title="接口目录" :description="`当前显示 ${filtered.length} 个接口`">
        <div class="filters">
          <el-input v-model="keyword" aria-label="搜索接口" placeholder="搜索接口路径或说明" clearable />
          <el-select v-model="group" aria-label="接口模块" placeholder="全部模块" clearable>
            <el-option v-for="item in groups" :key="item" :label="item" :value="item" />
          </el-select>
        </div>
        <EmptyState v-if="!filtered.length" title="没有匹配的接口" description="请更换关键词或模块筛选。" />
        <el-collapse v-else v-model="expanded">
          <el-collapse-item v-for="item in filtered" :key="item.key" :name="item.key">
            <template #title>
              <div class="operation-heading">
                <el-tag :type="item.method === 'GET' ? 'success' : item.method === 'DELETE' ? 'danger' : 'primary'" size="small">{{ item.method }}</el-tag>
                <code>{{ item.path }}</code><span>{{ item.summary || item.group }}</span>
              </div>
            </template>
            <div v-if="expanded.includes(item.key)" class="operation-body">
              <p v-if="item.description" class="guide">{{ item.description }}</p>
              <p>{{ (item.security ?? document.security)?.length ? '认证：需要登录凭证' : '认证：无需登录凭证' }}</p>
              <h3 v-if="item.parameters?.length">请求参数</h3>
              <div v-for="parameter in item.parameters" :key="`${parameter.in}:${parameter.name}`" class="parameter">
                <div><code>{{ parameter.name }}</code> · {{ parameter.in === 'path' ? '路径参数' : parameter.in === 'query' ? '查询参数' : parameter.in }} · {{ schemaType(parameter.schema, document) }} · {{ parameter.required ? '必填' : '选填' }}</div>
                <p v-if="parameter.description">{{ parameter.description }}</p>
              </div>
              <template v-if="item.requestBody">
                <h3>请求正文{{ item.requestBody.required ? '（必填）' : '' }}</h3>
                <div v-for="(content, mime) in item.requestBody.content" :key="mime">
                  <p>{{ mime }}</p><ApiSchemaView :schema="content.schema" :document="document" />
                </div>
              </template>
              <h3>响应</h3>
              <div v-for="(response, status) in item.responses" :key="status" class="response">
                <h4>{{ status }} · {{ responseDescription(response.description) }}</h4>
                <div v-for="(content, mime) in response.content" :key="mime">
                  <p>{{ mime }}</p><ApiSchemaView :schema="content.schema" :document="document" />
                </div>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </SectionCard>
    </template>
  </section>
</template>

<style scoped>
.documentation-page { min-width: 0; }
.guide { margin: 4px 0 12px; line-height: 1.7; overflow-wrap: anywhere; }
.filters { display: grid; grid-template-columns: minmax(0, 1fr) 220px; gap: 12px; margin-bottom: 20px; }
.operation-heading { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; min-width: 0; padding: 12px 0; text-align: left; line-height: 1.6; }
.operation-heading code { overflow-wrap: anywhere; }
.operation-heading span:last-child { color: var(--if-text-2); }
.operation-body { padding: 8px 4px 16px; min-width: 0; }
.operation-body h3 { margin: 20px 0 12px; }
.parameter, .response { margin-bottom: 12px; padding: 12px; background: var(--if-bg-page); border-radius: var(--if-radius-sm); overflow-wrap: anywhere; }
.response h4, .parameter p { margin: 0 0 8px; }
:deep(.el-collapse-item__header) { height: auto; min-height: 48px; }
:deep(.el-collapse-item__title) { min-width: 0; }
@media (max-width: 767px) { .filters { grid-template-columns: 1fr; } }
</style>
