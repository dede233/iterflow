<script setup lang="ts">
import { computed } from 'vue'
import { resolveSchema, schemaFields, schemaType } from '@/utils/apiDocumentation'
import type { ApiSchema, OpenApiDocument } from '@/utils/apiDocumentation'

const props = defineProps<{ schema?: ApiSchema; document: OpenApiDocument }>()
const fields = computed(() => schemaFields(props.schema, props.document))
const resolved = computed(() => resolveSchema(props.schema, props.document))
</script>

<template>
  <div class="api-schema">
    <p class="schema-type">数据类型：<code>{{ schemaType(schema, document) }}</code></p>
    <div v-if="fields.length" class="fields">
      <div v-for="field in fields" :key="field.name" class="field">
        <div class="field-heading"><code>{{ field.name }}</code><span>{{ field.type }}</span><el-tag v-if="field.required" size="small" type="warning">必填</el-tag></div>
        <p>{{ field.description }}</p>
      </div>
    </div>
    <details><summary>查看完整结构</summary><pre>{{ JSON.stringify(resolved, null, 2) }}</pre></details>
  </div>
</template>

<style scoped>
.api-schema { min-width: 0; }
.schema-type { margin: 6px 0 12px; color: var(--if-text-2); }
.fields { border: 1px solid var(--if-border); border-radius: var(--if-radius-sm); }
.field { padding: 10px 12px; border-bottom: 1px solid var(--if-border); }
.field:last-child { border-bottom: 0; }
.field-heading { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.field-heading code { font-weight: 600; overflow-wrap: anywhere; }
.field-heading span { color: var(--if-text-3); }
.field p { margin: 5px 0 0; color: var(--if-text-2); overflow-wrap: anywhere; }
details { margin-top: 12px; }
summary { color: var(--if-brand-600); cursor: pointer; }
pre { padding: 12px; background: var(--if-bg-page); border-radius: var(--if-radius-sm); white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
