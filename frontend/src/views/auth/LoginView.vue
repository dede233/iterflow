<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
  <main class="login" aria-labelledby="login-title">
    <el-card class="card" shadow="never">
      <h1 id="login-title">迭程 IterFlow</h1>
      <p>需求与版本协作管理系统</p>
      <el-form @submit.prevent="submit">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" autocomplete="username" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" show-password placeholder="密码" autocomplete="current-password" />
        </el-form-item>
        <el-button native-type="submit" type="primary" :loading="submitting" class="full-width">登录</el-button>
      </el-form>
    </el-card>
  </main>
</template>

<style scoped>
.login { min-height: 100vh; display: grid; place-items: center; background: linear-gradient(135deg, #eaf4ff, #f8fbff); }
.card { width: min(420px, 92vw); }
h1 { margin: 0 0 8px; font-size: 26px; }
p { margin: 0 0 24px; color: #64748b; }
.full-width { width: 100%; }
</style>
