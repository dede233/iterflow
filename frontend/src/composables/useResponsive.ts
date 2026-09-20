import { computed } from 'vue'
import { useMediaQuery } from '@vueuse/core'

export function useResponsive() {
  const isMobile = useMediaQuery('(max-width: 767px)')
  const isTablet = useMediaQuery('(min-width: 768px) and (max-width: 1199px)')
  const isDesktop = computed(() => !isMobile.value && !isTablet.value)
  return { isMobile, isTablet, isDesktop }
}
