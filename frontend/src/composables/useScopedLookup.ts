import { onScopeDispose, shallowRef, watch } from 'vue'
/** Optional scoped reads never change the parent object's availability. */
export function useScopedLookup<T>(identity: () => readonly [number | null | undefined, boolean, string], load: (id: number) => Promise<T>) {
  const value = shallowRef<T | null>(null)
  let sequence = 0
  watch(identity, async ([id, allowed]) => {
    const current = ++sequence
    value.value = null
    if (!allowed || id == null || !Number.isSafeInteger(id) || id <= 0) return
    try { const result = await load(id); if (current === sequence) value.value = result }
    catch { /* 403/404/network failure retains only the parent-provided ID. */ }
  }, { immediate: true, flush: 'sync' })
  onScopeDispose(() => { sequence++; value.value = null })
  return value
}
