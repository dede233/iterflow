<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AuthShell from '@/components/ui/AuthShell.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const forced = computed(() => auth.mustChangePassword)
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
  const wasForced = forced.value
  try {
    await auth.changePassword(form.currentPassword, form.newPassword)
    ElMessage.success('密码已修改，请继续使用系统')
    await router.replace(!wasForced && route.query.from === 'profile' ? '/profile' : '/')
  } catch {
    ElMessage.error('当前密码不正确，或新密码不符合要求')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthShell>
    <el-card class="password-card" shadow="never">
      <div class="eyebrow">账号安全</div>
      <h1 id="change-password-title">{{ forced ? '修改初始密码' : '修改密码' }}</h1>
      <p>{{ forced ? '为保护账号安全，请先设置一个新密码。' : '定期更新密码有助于保护账号安全。' }}</p>
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
  </AuthShell>
</template>

<style scoped>
.password-card { width: 100%; border-radius: var(--if-radius-lg) !important; box-shadow: var(--if-shadow) !important; }
.password-card :deep(.el-card__body) { padding: 34px; }
.eyebrow { margin-bottom: 8px; color: var(--if-brand-600); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
h1 { margin: 0 0 8px; font-size: 26px; }
p { margin: 0 0 28px; color: var(--if-text-2); font-size: 14px; line-height: 1.6; }
.full-width { width: 100%; min-height: 42px; margin-top: 8px; font-weight: 650; }
@media (max-width: 767px) { .password-card :deep(.el-card__body) { padding: 26px 22px; } }
</style>
