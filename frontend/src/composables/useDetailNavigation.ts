import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { detailTarget, listTarget, sanitizeInternalReturnTarget } from '@/utils/listQuery'
export function useDetailNavigation(defaultList: string) {
  const route = useRoute()
  // Embedded details share the list route, whose applied query is the return context.
  const backTo = computed(() => route.path === defaultList
    ? listTarget(defaultList, route.query)
    : sanitizeInternalReturnTarget(route.query?.return_to) ?? defaultList)
  return { backTo, related: (path: string) => detailTarget(path, backTo.value) }
}
