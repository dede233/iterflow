import { onBeforeUnmount, onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'

type UnsavedChangesOptions = {
  isDirty: () => boolean
  isBusy?: () => boolean
  active?: () => boolean
}

/** Keep drafts in their owning form; this guard never persists or clears them. */
export function useUnsavedChanges(options: UnsavedChangesOptions) {
  let pending: Promise<boolean> | null = null
  let disposed = false
  const active = () => !disposed && (options.active?.() ?? true)
  const busy = () => options.isBusy?.() ?? false

  async function requestLeave(): Promise<boolean> {
    if (!active()) return true
    if (busy()) return false
    if (!options.isDirty()) return true
    if (!pending) {
      pending = ElMessageBox.confirm('当前修改尚未保存，离开后将丢失。', '放弃未保存的修改？', {
        confirmButtonText: '放弃修改', cancelButtonText: '继续编辑', type: 'warning',
        distinguishCancelAndClose: true, closeOnClickModal: false,
      }).then(() => !disposed && !busy(), () => false).finally(() => { pending = null })
    }
    return pending
  }

  function beforeUnload(event: BeforeUnloadEvent): void {
    if (!active() || (!busy() && !options.isDirty())) return
    event.preventDefault()
    event.returnValue = ''
  }
  onMounted(() => window.addEventListener('beforeunload', beforeUnload))
  onBeforeUnmount(() => {
    disposed = true
    window.removeEventListener('beforeunload', beforeUnload)
  })
  return { requestLeave }
}
