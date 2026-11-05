<script setup lang="ts">
import { inject } from 'vue'
import { NodeViewWrapper, type NodeViewProps } from '@tiptap/vue-3'
import RequirementImage from './RequirementImage.vue'
defineProps<NodeViewProps>()
const announcementId = inject<() => number | undefined>('editorAnnouncementId')
const requirementId = inject<() => number | undefined>('editorRequirementId')
</script>
<template>
  <NodeViewWrapper><RequirementImage :file-id="node.attrs.fileId" :requirement-id="requirementId?.()" :announcement-id="announcementId?.()" /></NodeViewWrapper>
</template>
