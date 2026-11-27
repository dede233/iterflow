<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { getAdProductionImage } from '@/api/adProductions'
import AppIcon from '@/components/ui/AppIcon.vue'
import { AD_PRODUCTION_IMAGE_TYPES } from '@/constants/adProduction'

const props = defineProps<{
  source: { recordId: number; fileId: number; name: string } | { file: File }
  removeLabel?: string
  disabled?: boolean
}>()
defineEmits<{ remove: [] }>()

const name = computed(() => 'file' in props.source ? props.source.file.name : props.source.name)
const imageUrl = ref('')
const previewVisible = ref(false)
const loading = ref(true)
const failed = ref(false)
let controller: AbortController | undefined

function releaseUrl(): void {
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  imageUrl.value = ''
}

function imageFailed(): void {
  failed.value = true
  previewVisible.value = false
  releaseUrl()
}

async function load(): Promise<void> {
  controller?.abort()
  const current = new AbortController()
  controller = current
  loading.value = true
  failed.value = false
  releaseUrl()
  try {
    const source = props.source
    const image = 'file' in source ? source.file : await getAdProductionImage(source.recordId, source.fileId, current.signal)
    if (current.signal.aborted) return
    if (!AD_PRODUCTION_IMAGE_TYPES.includes(image.type)) {
      imageFailed()
      return
    }
    imageUrl.value = URL.createObjectURL(image)
  } catch {
    if (!current.signal.aborted) imageFailed()
  } finally {
    if (!current.signal.aborted) loading.value = false
  }
}

onMounted(load)
onBeforeUnmount(() => {
  controller?.abort()
  releaseUrl()
})
</script>

<template>
  <figure class="ad-image">
    <button
      v-if="imageUrl"
      type="button"
      class="image-surface"
      :data-testid="'fileId' in source ? `ad-production-image-${source.fileId}` : undefined"
      :aria-label="`预览 ${name}`"
      @click="previewVisible = true"
    >
      <img :src="imageUrl" alt="" @error="imageFailed" />
    </button>
    <div v-else class="image-surface image-placeholder" :aria-busy="loading">
      <AppIcon name="image" :size="24" />
      <span v-if="loading" role="status">加载中</span>
      <button v-else-if="failed" type="button" class="image-retry" :aria-label="`重新加载 ${name}`" @click="load">重试</button>
    </div>
    <figcaption class="image-name" :title="name">{{ name }}</figcaption>
    <el-button v-if="removeLabel" link type="danger" :disabled="disabled" :aria-label="`移除 ${name}`" class="image-remove" :data-testid="'fileId' in source ? `ad-production-remove-image-${source.fileId}` : undefined" @click="$emit('remove')">{{ removeLabel }}</el-button>

    <el-dialog v-model="previewVisible" append-to-body destroy-on-close :title="name" width="min(780px, calc(100vw - 32px))">
      <img v-if="imageUrl" class="image-preview" :src="imageUrl" :alt="name" />
      <template #footer><el-button @click="previewVisible = false">关闭预览</el-button></template>
    </el-dialog>
  </figure>
</template>

<style scoped>
.ad-image { display: grid; align-content: start; margin: 0; min-width: 0; gap: 4px; }
.image-surface {
  width: 100%;
  aspect-ratio: 4 / 3;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  place-items: center;
  overflow: hidden;
  padding: 0;
  border: 1px solid var(--if-border);
  border-radius: var(--if-radius-sm);
  background: var(--if-bg-subtle);
}
button.image-surface { cursor: zoom-in; }
.image-surface img { width: 100%; height: 100%; object-fit: cover; }
.image-surface:focus-visible, .image-retry:focus-visible { outline: 2px solid var(--if-brand-400); outline-offset: 2px; }
.image-placeholder { align-content: center; gap: 4px; color: var(--if-text-secondary); font-size: 12px; }
.image-retry { min-height: 44px; padding: 0 8px; border: 0; background: none; color: var(--el-color-primary); cursor: pointer; }
.image-name { min-width: 0; overflow-wrap: anywhere; color: var(--if-text-secondary); font-size: 12px; line-height: 1.3; }
.image-remove { justify-self: start; margin: 0; }
.image-preview { display: block; max-width: 100%; max-height: 68dvh; margin: 0 auto; object-fit: contain; }
@media (max-width: 767px) {
  .image-remove { min-height: 44px; min-width: 44px; }
}
</style>
