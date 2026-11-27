<script setup lang="ts">
import { inject } from 'vue'
import { NodeViewWrapper, type NodeViewProps } from '@tiptap/vue-3'
import RequirementImage from './RequirementImage.vue'
defineProps<NodeViewProps>()
const announcementId = inject<() => number | undefined>('editorAnnouncementId')
const requirementId = inject<() => number | undefined>('editorRequirementId')
const feedbackId = inject<() => number | undefined>('editorFeedbackId')
const adProductionId = inject<() => number | undefined>('editorAdProductionId')
</script>
<template>
  <NodeViewWrapper>
    <RequirementImage :file-id="node.attrs.fileId" :requirement-id="requirementId?.()" :announcement-id="announcementId?.()" :feedback-id="feedbackId?.()" :ad-production-id="adProductionId?.()" />
  </NodeViewWrapper>
</template>
