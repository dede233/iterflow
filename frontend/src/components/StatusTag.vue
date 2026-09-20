<script setup lang="ts">
import { computed } from 'vue'
const props=defineProps<{status:string}>()
const type=computed(()=>({ONLINE:'success',RELEASED:'success',DONE:'success',DEVELOPING:'primary',TESTING:'warning',READY:'warning',CANCELED:'info',CLOSED:'info'} as any)[props.status] ?? '')
</script>
<template><el-tag :type="type" effect="light">{{ status }}</el-tag></template>
