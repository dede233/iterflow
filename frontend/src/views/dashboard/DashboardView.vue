<template><div class="page"><div class="page-title">首页</div><el-row :gutter="12"><el-col :xs="12" :sm="6" v-for="item in items" :key="item.label"><el-card><div class="label">{{item.label}}</div><div class="value">{{item.value}}</div></el-card></el-col></el-row><el-card style="margin-top:16px"><h3>最近动态</h3><el-timeline><el-timeline-item timestamp="刚刚">V1.0.1 进入测试阶段</el-timeline-item><el-timeline-item timestamp="2小时前">FB-20260920-0003 已转为需求</el-timeline-item></el-timeline></el-card></div></template>
<script setup lang="ts">
const items = [
  { label: '待处理反馈', value: 12 },
  { label: '进行中需求', value: 28 },
  { label: '当前版本', value: 'V1.0.1' },
  { label: '累计发布', value: 18 },
]
</script>
<style scoped>.label{color:#64748b}.value{font-size:28px;font-weight:800;margin-top:8px}</style>
