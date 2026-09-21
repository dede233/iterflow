<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const submitting = ref(false)
const form = reactive({ currentPassword: '', newPassword: '', confirmPassword: '' })

async function submit(): Promise<void> {
  if (form.newPassword.length < 8) {
    ElMessage.warning('新密码至少需要 8 个字符')
    return
  }
  if (form.newPassword !== form.confirmPassword) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  submitting.value = true
  try {
    await auth.changePassword(form.currentPassword, form.newPassword)
    ElMessage.success('密码已修改，请继续使用系统')
    await router.replace('/')
  } catch {
    ElMessage.error('当前密码不正确，或新密码不符合要求')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="password-page" aria-labelledby="change-password-title">
    <el-card class="password-card" shadow="never">
      <h1 id="change-password-title">修改初始密码</h1>
      <p>为保护账号安全，请先设置一个新密码。</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="当前密码">
          <el-input v-model="form.currentPassword" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="form.newPassword" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="form.confirmPassword" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-button native-type="submit" type="primary" :loading="submitting" class="full-width">
          保存新密码
        </el-button>
      </el-form>
    </el-card>
  </main>
</template>

<style scoped>
.password-page { min-height: 100vh; display: grid; place-items: center; padding: 20px; background: #f5f7fa; }
.password-card { width: min(420px, 100%); }
h1 { margin: 0 0 8px; font-size: 22px; }
p { margin: 0 0 24px; color: #64748b; }
.full-width { width: 100%; }
</style>
