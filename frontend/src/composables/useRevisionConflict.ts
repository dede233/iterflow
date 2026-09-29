import { reactive, ref } from 'vue'
import {
  conflictReadError,
  revisionConflictData,
  type ConflictSummaryRow,
  type RevisionConflictData,
} from '@/types/revisionConflict'

export function useRevisionConflict() {
  const visible = ref(false)
  const loading = ref(false)
  const entityLabel = ref('')
  const submittedRevision = ref<number | string | null>(null)
  const metadata = ref<RevisionConflictData | null>(null)
  const summary = ref<ConflictSummaryRow[]>([])
  const readError = ref('')
  let loadLatest: (() => Promise<void>) | null = null
  let applyLatest: (() => Promise<void>) | null = null
  let sequence = 0

  async function show<T>(
    error: unknown,
    revision: number | string,
    options: {
      entityLabel: string
      getLatest: () => Promise<T>
      summarize: (latest: T) => ConflictSummaryRow[]
      apply: (latest: T) => void | Promise<void>
    },
  ): Promise<boolean> {
    const data = revisionConflictData(error)
    if (!data) return false
    const current = ++sequence
    visible.value = true
    entityLabel.value = options.entityLabel
    submittedRevision.value = revision
    metadata.value = data
    summary.value = []
    readError.value = ''
    loadLatest = async () => {
      const latest = await options.getLatest()
      if (current === sequence) summary.value = options.summarize(latest)
    }
    applyLatest = async () => {
      const latest = await options.getLatest()
      if (current === sequence) {
        await options.apply(latest)
        visible.value = false
        sequence++
      }
    }
    await readPreview()
    return true
  }

  async function readPreview(): Promise<void> {
    if (!loadLatest) return
    const current = sequence
    loading.value = true
    readError.value = ''
    try {
      await loadLatest()
    } catch (error) {
      if (current === sequence) readError.value = conflictReadError(error)
    } finally {
      if (current === sequence) loading.value = false
    }
  }

  async function reload(): Promise<void> {
    if (!applyLatest) return
    const current = sequence
    loading.value = true
    readError.value = ''
    try {
      await applyLatest()
    } catch (error) {
      if (current === sequence) readError.value = conflictReadError(error)
    } finally {
      if (current === sequence) loading.value = false
    }
  }

  function close(): void {
    visible.value = false
    loading.value = false
    sequence++
  }

  return reactive({ visible, loading, entityLabel, submittedRevision, metadata, summary, readError, show, reload, close })
}
