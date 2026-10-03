import { onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { detailTarget, listTarget, parseListQuery } from '@/utils/listQuery'

/** Draft controls are separate from the URL snapshot consumed by each request. */
export function useListQuery(options: {
  path: string
  readDraft: () => Record<string, unknown>
  restore: (query: Record<string, string>) => void
  load: () => Promise<void>
  invalidate: () => void
}) {
  const route = useRoute()
  const router = useRouter()
  let applied = parseListQuery(options.path, route.query)
  let disposed = false
  options.restore(applied)
  const reload = () => { if (!disposed) void options.load() }
  const stop = watch(() => route.query, () => {
    if (disposed || (route.path && route.path !== options.path)) return
    options.invalidate()
    applied = parseListQuery(options.path, route.query)
    options.restore(applied)
    reload()
  }, { flush: 'sync' })
  onMounted(reload)
  onBeforeUnmount(() => { disposed = true; stop(); options.invalidate() })
  async function publish(query: Record<string, unknown>) {
    if (disposed || (route.path && route.path !== options.path)) return
    const next = parseListQuery(options.path, query)
    // Even applying identical fields must invalidate an older request/retry.
    options.invalidate()
    applied = next
    options.restore(next)
    const routeEntries = Object.entries(route.query)
    const same = routeEntries.length === Object.keys(next).length && routeEntries.every(([key, value]) => typeof value === 'string' && next[key] === value)
    if (same) reload()
    else await router.push({ path: options.path, query: next })
  }
  return {
    applied: () => ({ ...applied }),
    apply: () => publish({ ...options.readDraft(), page: 1 }),
    reset: () => publish({}),
    paginate: (page: number) => publish({ ...applied, page }),
    detail: (path: string) => detailTarget(path, listTarget(options.path, applied)),
  }
}
