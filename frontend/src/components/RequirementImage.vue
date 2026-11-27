<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api } from '@/api/client'
import { pendingImage } from '@/utils/requirementImages'
const props = defineProps<{
  fileId: string
  requirementId?: number
  announcementId?: number
  feedbackId?: number
  adProductionId?: number
}>()
const source = computed(() => {
  if (props.announcementId) return { path: `/announcements/${props.announcementId}/images`, label: '公告图片' }
  if (props.feedbackId) return { path: `/feedbacks/${props.feedbackId}/images`, label: '反馈图片' }
  if (props.adProductionId) return { path: `/ad-productions/${props.adProductionId}/content-images`, label: '物料制作图片' }
  if (props.requirementId) return { path: `/requirements/${props.requirementId}/images`, label: '需求图片' }
  return undefined
})
const imageLabel = computed(() => source.value?.label ?? '正文图片')
const url = ref('')
const failed = ref(false)
const dialog = ref<HTMLDialogElement>()
watch(() => [props.fileId, source.value] as const, async ([fileId, imageSource], _, cleanup) => {
  let active = true
  let objectUrl = ''
  url.value = ''
  failed.value = false
  cleanup(() => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl) })
  try {
    const blob = fileId.startsWith('local-') ? pendingImage(fileId) : imageSource ?
      (await api.get<Blob>(`${imageSource.path}/${fileId}`, { responseType: 'blob' })).data : undefined
    if (!active) return
    if (!blob) { failed.value = true; return }
    objectUrl = URL.createObjectURL(blob)
    url.value = objectUrl
  } catch { if (active) failed.value = true }
}, { immediate: true })
</script>
<template>
  <span class="requirement-image" contenteditable="false">
    <button v-if="url" type="button" aria-label="查看大图" @click="dialog?.showModal()"><img :src="url" :alt="imageLabel"></button>
    <span v-else>{{ failed ? '图片无法读取' : '正在载入图片…' }}</span>
    <dialog ref="dialog" :aria-label="`${imageLabel}大图`" @click.self="dialog?.close()">
      <button type="button" autofocus @click="dialog?.close()">关闭</button>
      <img v-if="url" :src="url" :alt="`${imageLabel}大图`">
    </dialog>
  </span>
</template>
<style scoped>
.requirement-image { display: block; max-width: 100%; }
.requirement-image > button { display: grid; place-items: center; min-width: 44px; min-height: 44px; max-width: 100%; padding: 0; border: 0; background: transparent; cursor: zoom-in; }
.requirement-image > button img { display: block; max-width: 100%; max-height: 20rem; object-fit: contain; }
dialog { max-width: 96vw; max-height: 96vh; box-sizing: border-box; border: 0; border-radius: 8px; padding: .75rem; }
dialog::backdrop { background: #141820bb; }
dialog img { display: block; max-width: 90vw; max-height: 82vh; object-fit: contain; }
dialog button { display: block; margin: 0 0 .5rem auto; }
</style>
