<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { getFeedback } from '@/api/feedbacks'
import { getRequirement } from '@/api/requirements'
import { getVersion } from '@/api/versions'
import { useScopedLookup } from '@/composables/useScopedLookup'
import { detailTarget } from '@/utils/listQuery'
const props = defineProps<{ kind: 'feedback' | 'requirement' | 'version'; id?: number | null; returnTo: string; parentIdentity: string; fallback?: string; linkLabel?: string }>()
const auth = useAuthStore()
const domains = { feedback: 'feedbacks', requirement: 'requirements', version: 'versions' }
const label = useScopedLookup(
  () => [props.id, auth.hasPermission(`rd.${props.kind}.view`), `${props.parentIdentity}:${props.kind}:${auth.user?.id}:${auth.accessToken}:${auth.permissionCodes.join(',')}`] as const,
  async id => {
    const target = props.kind === 'feedback' ? await getFeedback(id) : props.kind === 'requirement' ? await getRequirement(id) : await getVersion(id)
    if (target.id !== id) throw new Error('Target identity changed')
    return 'version_no' in target ? `${target.version_no} · ${target.name}` : 'requirement_no' in target ? `${target.requirement_no} · ${target.title}` : `${target.feedback_no} · ${target.title}`
  },
)
</script>
<template>
  <span class="relation">
    <RouterLink v-if="label" :to="detailTarget(`/${domains[kind]}/${id}`, returnTo)" class="relation-link">{{ linkLabel || label }}</RouterLink>
    <span v-else>{{ id == null ? '—' : (fallback || `#${id}`) }}</span>
  </span>
</template>
<style scoped>
.relation { overflow-wrap: anywhere; }
.relation-link { color: var(--if-brand-500); }
.relation-link:focus-visible { outline: 2px solid var(--if-brand-500); outline-offset: 2px; }
</style>
