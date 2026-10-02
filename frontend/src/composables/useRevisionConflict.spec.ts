import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useRevisionConflict } from './useRevisionConflict'
import { isRevisionConflict, revisionConflictData } from '@/types/revisionConflict'

const metadata = {
  current_revision: 2,
  current_updated_at: '2026-09-29T01:00:00Z',
  current_updated_by: 8,
}
const stale = { response: { status: 409, data: { code: 40910, data: metadata } } }
const business = { response: { status: 409, data: { code: 40923 } } }
const wrappers: ReturnType<typeof mount>[] = []

function setup() {
  let conflict!: ReturnType<typeof useRevisionConflict>
  const host = defineComponent({
    setup() {
      conflict = useRevisionConflict()
      return () => h('div')
    },
  })
  wrappers.push(mount(host))
  return conflict
}

afterEach(() => {
  for (const wrapper of wrappers.splice(0)) wrapper.unmount()
})

describe('revision conflict identification and explicit reload', () => {
  it('recognizes only HTTP 409 with code 40910', () => {
    expect(isRevisionConflict(stale)).toBe(true)
    expect(revisionConflictData(stale)).toEqual(metadata)
    expect(isRevisionConflict(business)).toBe(false)
    expect(isRevisionConflict({ response: { status: 422, data: { code: 40910 } } })).toBe(false)
    expect(revisionConflictData(business)).toBeNull()
  })

  it('reads a safe summary without applying server data until reload', async () => {
    const conflict = setup()
    const apply = vi.fn()
    const getLatest = vi.fn().mockResolvedValue({ title: '服务器标题', revision: 2 })
    const options = {
      entityLabel: '反馈',
      getLatest,
      summarize: (item: { title: string }) => [{ label: '标题', value: item.title }],
      apply,
    }
    expect(await conflict.show(business, 1, options)).toBe(false)
    expect(conflict.visible).toBe(false)
    expect(await conflict.show(stale, 1, options)).toBe(true)
    expect(conflict.summary).toEqual([{ label: '标题', value: '服务器标题' }])
    expect(conflict.submittedRevision).toBe(1)
    expect(apply).not.toHaveBeenCalled()
    conflict.close()
    expect(apply).not.toHaveBeenCalled()
    await conflict.show(stale, 1, options)
    await conflict.reload()
    expect(getLatest).toHaveBeenCalledTimes(3)
    expect(apply).toHaveBeenCalledExactlyOnceWith({ title: '服务器标题', revision: 2 })
    expect(conflict.visible).toBe(false)
    expect(conflict.loading).toBe(false)

    const nextRead = Promise.resolve({ title: '新的服务器内容', revision: 3 })
    const next = conflict.show(stale, 2, { ...options, getLatest: () => nextRead })
    expect(conflict.visible).toBe(true)
    expect(conflict.loading).toBe(true)
    expect(conflict.summary).toEqual([])
    await next
    expect(conflict.visible).toBe(true)
    expect(conflict.loading).toBe(false)
    expect(conflict.submittedRevision).toBe(2)
    expect(conflict.summary).toEqual([{ label: '标题', value: '新的服务器内容' }])
    await conflict.reload()
    expect(conflict.visible).toBe(false)
    expect(conflict.loading).toBe(false)
    expect(apply).toHaveBeenLastCalledWith({ title: '新的服务器内容', revision: 3 })
  })

  it.each([403, 404, 500])('keeps the dialog and clears loading after a %i detail GET', async (status) => {
    const conflict = setup()
    const readError = status === 500
      ? '暂时无法读取服务器版本，请检查网络后重试'
      : '该记录已不可访问或不存在'
    const apply = vi.fn()
    const getLatest = vi.fn().mockRejectedValue({ response: { status } })
    await conflict.show(stale, 1, {
      entityLabel: '需求',
      getLatest,
      summarize: () => [],
      apply,
    })
    expect(conflict.visible).toBe(true)
    expect(conflict.readError).toBe(readError)
    expect(conflict.summary).toEqual([])
    await conflict.reload()
    expect(conflict.visible).toBe(true)
    expect(conflict.loading).toBe(false)
    expect(conflict.readError).toBe(readError)
    expect(apply).not.toHaveBeenCalled()
  })

  it.each([false, true])('ignores a late reload after closing (new conflict: %s)', async (showNext) => {
    const conflict = setup()
    let resolveOld!: (value: { title: string }) => void
    const oldRead = new Promise<{ title: string }>((resolve) => { resolveOld = resolve })
    const apply = vi.fn()
    const options = {
      entityLabel: '反馈',
      getLatest: vi.fn().mockResolvedValueOnce({ title: '初始摘要' }).mockReturnValueOnce(oldRead),
      summarize: (item: { title: string }) => [{ label: '标题', value: item.title }],
      apply,
    }
    await conflict.show(stale, 1, options)
    const pending = conflict.reload()
    expect(conflict.loading).toBe(true)
    conflict.close()
    let resolveNext!: (value: { title: string }) => void
    const nextRead = new Promise<{ title: string }>((resolve) => { resolveNext = resolve })
    const next = showNext
      ? conflict.show(stale, 2, { ...options, getLatest: () => nextRead })
      : null
    resolveOld({ title: '过期的服务器内容' })
    await pending
    expect(apply).not.toHaveBeenCalled()
    expect(conflict.visible).toBe(showNext)
    expect(conflict.loading).toBe(showNext)
    expect(conflict.summary).toEqual(showNext ? [] : [{ label: '标题', value: '初始摘要' }])
    expect(conflict.readError).toBe('')
    resolveNext({ title: '新的服务器内容' })
    await next
    if (showNext) {
      expect(conflict.loading).toBe(false)
      expect(conflict.summary).toEqual([{ label: '标题', value: '新的服务器内容' }])
    }
    conflict.close()
  })

  it('does not close a new conflict when an earlier async apply finishes', async () => {
    const conflict = setup()
    let finishApply!: () => void
    const applying = new Promise<void>((resolve) => { finishApply = resolve })
    const apply = vi.fn(() => applying)
    const options = {
      entityLabel: '需求',
      getLatest: async () => ({ title: '旧摘要' }),
      summarize: (item: { title: string }) => [{ label: '标题', value: item.title }],
      apply,
    }
    await conflict.show(stale, 1, options)
    const pending = conflict.reload()
    await Promise.resolve()
    expect(apply).toHaveBeenCalledOnce()
    await conflict.show(stale, 2, { ...options, getLatest: async () => ({ title: '新摘要' }) })
    finishApply()
    await pending
    expect(conflict.visible).toBe(true)
    expect(conflict.loading).toBe(false)
    expect(conflict.submittedRevision).toBe(2)
    expect(conflict.summary).toEqual([{ label: '标题', value: '新摘要' }])
  })

  it('ignores a late preview from a conflict that was already closed', async () => {
    const conflict = setup()
    let resolveOld!: (value: { title: string }) => void
    const oldRead = new Promise<{ title: string }>((resolve) => { resolveOld = resolve })
    const options = (getLatest: () => Promise<{ title: string }>) => ({
      entityLabel: '反馈',
      getLatest,
      summarize: (item: { title: string }) => [{ label: '标题', value: item.title }],
      apply: vi.fn(),
    })
    const pending = conflict.show(stale, 1, options(() => oldRead))
    conflict.close()
    await conflict.show(stale, 2, options(async () => ({ title: '新的服务器内容' })))
    resolveOld({ title: '过期的服务器内容' })
    await pending
    expect(conflict.visible).toBe(true)
    expect(conflict.loading).toBe(false)
    expect(conflict.summary).toEqual([{ label: '标题', value: '新的服务器内容' }])
  })
})
