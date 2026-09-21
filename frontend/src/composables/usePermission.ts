import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

export function usePermission() {
  const auth = useAuthStore()

  return {
    can: (permission: string | string[]) => auth.hasPermission(permission),
    permissions: computed(() => auth.permissionCodes),
  }
}
