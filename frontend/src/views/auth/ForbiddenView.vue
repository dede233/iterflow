<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <main class="forbidden-page">
    <el-result icon="warning" title="无权访问" sub-title="你的账号没有访问此页面所需的权限。">
      <template #extra>
        <el-button type="primary" @click="router.replace('/')">返回首页</el-button>
      </template>
    </el-result>
  </main>
</template>

<style scoped>
.forbidden-page { min-height: 100vh; display: grid; place-items: center; }
</style>
