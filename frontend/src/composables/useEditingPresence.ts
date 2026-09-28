import { onBeforeUnmount, ref } from 'vue'
import {
  editingHeartbeat,
  endEditing,
  startEditing,
  type EditingEntityType,
  type ExistingEditor,
} from '@/api/editing'

const HEARTBEAT_INTERVAL_MS = 120_000

interface EditingSession {
  started: boolean
  heartbeatInFlight: boolean
  timer?: ReturnType<typeof setInterval>
}

/** Serialize session requests so end cannot race with start or heartbeat. */
export function useEditingPresence(entityType: EditingEntityType, entityId: number) {
  const existingEditor = ref<ExistingEditor | null>(null)
  const isStarting = ref(false)
  const isActive = ref(false)
  let current: EditingSession | null = null
  let queue: Promise<void> = Promise.resolve()

  function enqueue(operation: () => Promise<void>): Promise<void> {
    const result = queue.then(operation)
    queue = result.catch(() => undefined)
    return result
  }

  function heartbeat(session: EditingSession): void {
    if (current !== session || session.heartbeatInFlight) return
    session.heartbeatInFlight = true
    void enqueue(async () => {
      try {
        if (current !== session) return
        const response = await editingHeartbeat(entityType, entityId)
        if (current === session) existingEditor.value = response.existing_editor
      } catch {
        // A failed hint never interrupts editing.
      } finally {
        session.heartbeatInFlight = false
      }
    })
  }

  function stop(): Promise<void> {
    const session = current
    if (!session) return Promise.resolve()
    current = null
    isActive.value = false
    isStarting.value = false
    existingEditor.value = null
    if (session.timer) clearInterval(session.timer)
    return enqueue(async () => {
      if (!session.started) return
      try {
        await endEditing(entityType, entityId)
      } catch {
        // Redis TTL releases a marker if this best-effort request fails.
      }
    })
  }

  function start(): Promise<void> {
    if (current) void stop()
    const session: EditingSession = { started: false, heartbeatInFlight: false }
    current = session
    isActive.value = true
    isStarting.value = true
    existingEditor.value = null
    return enqueue(async () => {
      try {
        const response = await startEditing(entityType, entityId)
        session.started = true
        if (current !== session) return
        existingEditor.value = response.existing_editor
        session.timer = setInterval(() => heartbeat(session), HEARTBEAT_INTERVAL_MS)
      } catch {
        // A failed hint must not block form editing or saving.
      } finally {
        if (current === session) isStarting.value = false
      }
    })
  }

  onBeforeUnmount(() => {
    void stop()
  })

  return { start, stop, existingEditor, isStarting, isActive }
}
