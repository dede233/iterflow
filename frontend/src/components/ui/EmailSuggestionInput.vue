<script setup lang="ts">
import { useResizeObserver } from '@vueuse/core'
import { ElInput, ElPopper, ElPopperContent } from 'element-plus'
import { computed, onMounted, ref, useId, watch } from 'vue'

defineOptions({ inheritAttrs: false })
const email = defineModel<string>({ required: true })
const props = withDefaults(defineProps<{
  id?: string
  maxlength?: number | string
  disabled?: boolean
  readonly?: boolean
}>(), { maxlength: 254, disabled: undefined })

const domains = [
  'qq.com', '163.com', 'gmail.com', 'foxmail.com', '126.com',
  'aliyun.com', 'outlook.com', 'hotmail.com', 'icloud.com', '139.com', '189.cn',
]
const listboxId = `email-suggestions-${useId()}`
const anchor = ref<HTMLElement | null>(null)
const popupTarget = ref<HTMLElement | null>(null)
const list = ref<HTMLUListElement | null>(null)
const inputWidth = ref(0)
const expanded = ref(false)
const activeIndex = ref(-1)

const suggestions = computed(() => {
  const [localPart, partialDomain = '', extra] = email.value.split('@')
  if (extra !== undefined || localPart.length > 64 ||
      !/^[a-z\d!#$%&'*+\/=?^_`{|}~.-]+$/i.test(localPart) ||
      localPart.split('.').some((part) => !part)) return []

  const prefix = partialDomain.toLowerCase()
  if (domains.includes(prefix)) return []
  return domains
    .filter((domain) => domain.startsWith(prefix))
    .map((domain) => `${localPart}@${domain}`)
    .filter((address) => address.length <= Number(props.maxlength))
})
const visible = computed(() => expanded.value && !props.disabled && !props.readonly && suggestions.value.length > 0)
const optionId = (index: number) => `${listboxId}-${index}`

onMounted(() => {
  popupTarget.value = anchor.value?.closest<HTMLElement>('[role="dialog"][aria-modal="true"]') ?? document.body
})
useResizeObserver(anchor, ([entry]) => { inputWidth.value = entry.contentRect.width })

watch(suggestions, () => {
  activeIndex.value = -1
  if (list.value) list.value.scrollTop = 0
})
watch(activeIndex, (index) => {
  const option = list.value?.children.item(index) as HTMLElement | null | undefined
  if (!list.value || !option) return

  const optionBottom = option.offsetTop + option.offsetHeight
  if (option.offsetTop < list.value.scrollTop) list.value.scrollTop = option.offsetTop
  else if (optionBottom > list.value.scrollTop + list.value.clientHeight) {
    list.value.scrollTop = optionBottom - list.value.clientHeight
  }
}, { flush: 'post' })

function open() {
  inputWidth.value = anchor.value?.getBoundingClientRect().width ?? 0
  expanded.value = true
}

function close() {
  expanded.value = false
  activeIndex.value = -1
}

function select(address: string) {
  email.value = address
  close()
}

function handleKeydown(event: Event) {
  if (!(event instanceof KeyboardEvent) || event.isComposing || event.keyCode === 229) return

  if (event.key === 'Escape' && visible.value) {
    event.preventDefault()
    event.stopPropagation()
    close()
    return
  }
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return

  const count = suggestions.value.length
  if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && count && !props.disabled && !props.readonly) {
    event.preventDefault()
    if (!visible.value) open()
    const step = event.key === 'ArrowDown' ? 1 : -1
    const index = activeIndex.value === -1 && step === -1 ? 0 : activeIndex.value
    activeIndex.value = (index + step + count) % count
  } else if (event.key === 'Enter' && visible.value && activeIndex.value >= 0) {
    event.preventDefault()
    event.stopPropagation()
    select(suggestions.value[activeIndex.value])
  } else if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
    activeIndex.value = -1
  }
}
</script>

<template>
  <div ref="anchor" class="email-suggestion-input">
    <ElInput
      v-bind="$attrs"
      :id="id"
      v-model="email"
      type="email"
      inputmode="email"
      autocomplete="email"
      :maxlength="maxlength"
      :disabled="disabled"
      :readonly="readonly"
      container-role="combobox"
      aria-autocomplete="list"
      :aria-expanded="visible"
      :aria-controls="visible ? listboxId : undefined"
      :aria-activedescendant="visible && activeIndex >= 0 ? optionId(activeIndex) : undefined"
      @focus="open"
      @input="open"
      @blur="close"
      @keydown="handleKeydown"
    />
    <Teleport v-if="visible && popupTarget" :to="popupTarget">
      <ElPopper role="listbox">
        <ElPopperContent
          :id="listboxId"
          :reference-el="anchor ?? undefined"
          effect="light"
          aria-label="邮箱建议"
          placement="bottom-start"
          :fallback-placements="['top-start']"
          :offset="4"
          popper-class="email-suggestion-popper"
          :popper-style="{ width: `${inputWidth}px` }"
          visible
        >
          <ul ref="list" class="email-suggestions" role="presentation" @mousedown.prevent>
            <li
              v-for="(address, index) in suggestions"
              :id="optionId(index)"
              :key="address"
              role="option"
              :aria-selected="activeIndex === index"
              @click="select(address)"
            >
              {{ address }}
            </li>
          </ul>
        </ElPopperContent>
      </ElPopper>
    </Teleport>
  </div>
</template>

<style scoped>
.email-suggestion-input { width: 100%; min-width: 0; }
:global(.el-popper.email-suggestion-popper) {
  overflow: hidden;
  padding: 0;
  border-radius: var(--if-radius);
  box-shadow: var(--if-shadow-md);
}
.email-suggestions {
  position: relative;
  max-height: min(240px, 40dvh);
  margin: 0;
  padding: 4px 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  list-style: none;
  color: var(--if-text-primary);
  font-size: 14px;
}
.email-suggestions li {
  display: flex;
  align-items: center;
  min-height: 36px;
  padding: 6px 12px;
  overflow-wrap: anywhere;
  line-height: 20px;
  cursor: pointer;
}
.email-suggestions li:hover,
.email-suggestions li[aria-selected="true"] {
  background-color: var(--if-info-bg);
  color: var(--if-info-fg);
}
@media (max-width: 767px), (pointer: coarse) {
  .email-suggestions li,
  .email-suggestion-input :deep(.el-input__wrapper) { min-height: 44px; }
}
@media (max-width: 767px) {
  .email-suggestion-input :deep(.el-input__inner) { font-size: 16px; }
}
</style>
