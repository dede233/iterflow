<script setup lang="ts">
import { useRouter } from 'vue-router'
import AuthShell from '@/components/ui/AuthShell.vue'
import AppIcon from '@/components/ui/AppIcon.vue'

const router = useRouter()
</script>

<template>
  <AuthShell>
    <section class="forbidden-card">
      <span class="icon"><AppIcon name="lock" :size="26" /></span>
      <div class="eyebrow">访问受限</div>
      <h1>无权访问</h1>
      <p>当前账号无权访问此功能。</p>
      <el-button type="primary" @click="router.replace('/')">返回首页</el-button>
    </section>
  </AuthShell>
</template>

<style scoped>
.forbidden-card { padding: 38px; border: 1px solid var(--if-border); border-radius: var(--if-radius-lg); background: var(--if-bg-surface); box-shadow: var(--if-shadow); }
.icon { display: grid; place-items: center; width: 54px; height: 54px; margin-bottom: 20px; border-radius: 15px; background: var(--if-warning-bg); color: var(--if-warning-fg); }
.eyebrow { color: var(--if-warning-fg); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
h1 { margin: 8px 0; font-size: 26px; }
p { margin: 0 0 24px; color: var(--if-text-2); }
@media (max-width: 767px) { .forbidden-card { padding: 28px 22px; } }
</style>
