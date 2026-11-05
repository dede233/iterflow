<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{ number: string }>()
const numberText = ref<HTMLElement>()

async function copyNumber() {
  try {
    await navigator.clipboard.writeText(props.number)
    ElMessage.success('需求编号已复制')
  } catch {
    const selection = window.getSelection()
    if (numberText.value && selection) {
      const range = document.createRange()
      range.selectNodeContents(numberText.value)
      selection.removeAllRanges()
      selection.addRange(range)
    }
    ElMessage.info('请手动复制需求编号')
  }
}
</script>

<template>
  <div class="requirement-number">
    <span>需求编号</span>
    <strong ref="numberText">{{ number }}</strong>
    <el-button link type="primary" @click="copyNumber">复制编号</el-button>
  </div>
</template>

<style scoped>
.requirement-number { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 8px; color: var(--if-text-2); font: 14px/1.5 var(--if-font-sans, sans-serif); }
strong { color: var(--if-text-1); font-family: var(--if-font-mono); user-select: all; }
</style>
