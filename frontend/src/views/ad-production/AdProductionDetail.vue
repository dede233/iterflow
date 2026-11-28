<script setup lang="ts">
import { computed } from 'vue'
import type { AdProduction } from '@/api/adProductions'
import RichTextContent from '@/components/RichTextContent.vue'
import StatusTag from '@/components/StatusTag.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import { AD_PRODUCTION_PUBLISHER_LABEL, adProductionStatusDisplay } from '@/constants/adProduction'
import { formatLocalDateTime } from '@/utils/dates'
import AdProductionImage from './AdProductionImage.vue'
import { adProductionTitle, ccUserNames, designerName, publisherName } from './adProductionDisplay'

const props = defineProps<{ record: AdProduction }>()
const status = computed(() => adProductionStatusDisplay(props.record.kind ?? 'MATERIAL', props.record.status))
</script>

<template>
  <div class="record-content">
    <SectionCard>
      <h2 class="detail-title">{{ adProductionTitle(record) }}</h2>
      <dl class="detail-meta">
        <div><dt>{{ AD_PRODUCTION_PUBLISHER_LABEL }}</dt><dd>{{ publisherName(record) }}</dd></div>
        <div><dt>需求接收人</dt><dd>{{ designerName(record, 'receiver_id') }}</dd></div>
        <div><dt>抄送人</dt><dd>{{ ccUserNames(record) }}</dd></div>
        <div><dt>发布时间</dt><dd><time :datetime="record.created_at">{{ formatLocalDateTime(record.created_at) }}</time></dd></div>
        <div><dt>截止时间</dt><dd><time v-if="record.due_at" :datetime="record.due_at">{{ formatLocalDateTime(record.due_at) }}</time><template v-else>—</template></dd></div>
        <div><dt>状态</dt><dd><StatusTag :status="record.status" :label="status.label" :type="status.tone" /></dd></div>
        <div v-if="record.status === 'COMPLETED'"><dt>实际完成人</dt><dd>{{ designerName(record, 'completed_by_id') }}</dd></div>
      </dl>
      <div class="detail-content">
        <h3>需求内容</h3>
        <RichTextContent :key="record.id" :ad-production-id="record.id" :content="record.content" :format="record.content_format" />
      </div>
      <div v-if="record.kind === 'MERCHANT_AD' && record.status === 'COMPLETED' && record.processing_result" class="detail-content">
        <h3>处理结果</h3>
        <p class="processing-result">{{ record.processing_result }}</p>
      </div>
    </SectionCard>
    <SectionCard title="图片">
      <div v-if="record.images.length" class="ad-image-grid">
        <AdProductionImage
          v-for="image in record.images"
          :key="`${record.id}-${image.file_id}`"
          :source="{ recordId: record.id, fileId: image.file_id, name: image.original_name }"
        />
      </div>
      <p v-else class="no-images">暂无图片</p>
    </SectionCard>
  </div>
</template>

<style scoped>
.record-content { container-type: inline-size; }
.detail-title { margin: 0 0 var(--if-space-4); font-size: 18px; overflow-wrap: anywhere; }
.detail-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--if-space-3); margin: 0 0 var(--if-space-4); }
.detail-meta dt { margin-bottom: 4px; color: var(--if-text-secondary); font-size: 12px; }
.detail-meta dd { min-height: 22px; margin: 0; overflow-wrap: anywhere; }
.detail-content { padding-top: var(--if-space-4); border-top: 1px solid var(--if-border); }
.detail-content h3 { margin: 0 0 var(--if-space-2); font-size: 14px; }
.processing-result { margin: 0; overflow-wrap: anywhere; white-space: pre-wrap; }
.ad-image-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 108px), 1fr)); gap: var(--if-space-3); }
.no-images { margin: 0; color: var(--if-text-secondary); }
@container (max-width: 420px) {
  .detail-meta { grid-template-columns: minmax(0, 1fr); }
}
</style>
