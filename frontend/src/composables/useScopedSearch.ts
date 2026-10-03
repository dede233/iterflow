import { onScopeDispose, reactive, watch } from 'vue'
export interface SelectionOption { id: number; code: string; title: string; status: string }
export function useScopedSearch(identity: () => readonly [boolean, string], fetchPage: (keyword: string, page: number) => Promise<{ items: SelectionOption[]; total: number }>) {
  const state = reactive({ open: false, keyword: '', page: 1, total: 0, items: [] as SelectionOption[], loading: false, error: false })
  let sequence = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  let disposed = false
  function invalidate() { sequence++; if (timer) clearTimeout(timer); timer = undefined; state.loading = false }
  function close() { invalidate(); state.open = false; state.items = []; state.total = 0; state.error = false }
  async function load() {
    invalidate()
    const current = sequence
    if (disposed || !state.open || !identity()[0]) return
    state.loading = true; state.error = false
    try {
      const result = await fetchPage(state.keyword.trim(), state.page)
      if (current !== sequence) return
      state.items = result.items; state.total = result.total
    } catch { if (current === sequence) { state.error = true; state.items = []; state.total = 0 } }
    finally { if (current === sequence) state.loading = false }
  }
  function open() { close(); if (disposed || !identity()[0]) return; state.open = true; state.keyword = ''; state.page = 1; void load() }
  function search(keyword: string) {
    invalidate(); state.keyword = keyword; state.page = 1; state.items = []; state.total = 0; state.error = false
    if (!state.open || !identity()[0]) return
    state.loading = true
    timer = setTimeout(() => { timer = undefined; void load() }, 250)
  }
  function paginate(page: number) { state.page = page; void load() }
  watch(identity, close, { flush: 'sync' })
  onScopeDispose(() => { disposed = true; close() })
  return { state, open, close, search, paginate, retry: load }
}
