import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { detailTarget, sanitizeInternalReturnTarget } from '@/utils/listQuery'
export function useDetailNavigation(defaultList: string) {
  const route = useRoute()
  const backTo = computed(() => sanitizeInternalReturnTarget(route.query?.return_to) ?? defaultList)
  return { backTo, related: (path: string) => detailTarget(path, backTo.value) }
}
