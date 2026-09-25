<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AuthShell from '@/components/ui/AuthShell.vue'

const form = reactive({ username: '', password: '' })
const submitting = ref(false)
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

async function submit(): Promise<void> {
  submitting.value = true
  try {
    const user = await auth.login(form.username, form.password)
    ElMessage.success(`欢迎回来，${user.display_name}`)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(user.must_change_password ? '/change-password' : redirect)
  } catch {
    ElMessage.error('用户名或密码错误，或账号已被停用')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthShell>
    <el-card class="card" shadow="never">
      <div class="eyebrow">欢迎回来</div>
      <h1 id="login-title">迭程 IterFlow</h1>
      <p>使用你的团队账号登录。</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="用户名" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="密码" autocomplete="current-password" />
        </el-form-item>
        <el-button native-type="submit" type="primary" :loading="submitting" class="full-width">登录</el-button>
      </el-form>
    </el-card>
  </AuthShell>
</template>

<style scoped>
.card { width: 100%; border-radius: var(--if-radius-lg) !important; box-shadow: var(--if-shadow) !important; }
.card :deep(.el-card__body) { padding: 34px; }
.eyebrow { margin-bottom: 8px; color: var(--if-brand-600); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
h1 { margin: 0 0 8px; font-size: 27px; line-height: 1.3; }
p { margin: 0 0 30px; color: var(--if-text-2); font-size: 14px; }
.full-width { width: 100%; min-height: 42px; margin-top: 8px; font-weight: 650; }
@media (max-width: 767px) { .card :deep(.el-card__body) { padding: 26px 22px; } }
</style>
