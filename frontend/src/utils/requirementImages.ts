import { createRequestId } from './requestId'

// New pictures stay in the editor until the containing record is saved.
const pending = new Map<string, File>()
export function rememberImage(file: File) {
  const key = 'local-' + createRequestId()
  pending.set(key, file)
  return key
}
export function forgetImage(key: string) { pending.delete(key) }
export function pendingImage(key: string) { return pending.get(key) }
export function editorImageEntries(html: string): [string, File][] {
  if (!html.includes('data-file-id="local-')) return []
  const parsed = document.createElement('template')
  parsed.innerHTML = html
  const refs = new Set(Array.from(parsed.content.querySelectorAll('img[data-file-id^="local-"]'), img => img.getAttribute('data-file-id')!))
  let total = 0
  return Array.from(refs, (key): [string, File] => {
    const file = pending.get(key)
    if (!file) throw new Error('请重新插入未载入的图片')
    total += file.size
    if (total > 8 * 1024 * 1024) throw new Error('本次新增图片总计不能超过 8 MiB')
    return [key, file]
  })
}
export async function withDescriptionImages<T extends { description?: string | null; description_format?: string }>(payload: T) {
  if (payload.description_format !== 'HTML' || !payload.description) return payload
  const entries = editorImageEntries(payload.description)
  if (!entries.length) return payload
  const images: Record<string, string> = {}
  for (const [key, file] of entries) {
    images[key] = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result))
      reader.onerror = () => reject(new Error('图片读取失败'))
      reader.readAsDataURL(file)
    })
  }
  return { ...payload, description_images: images }
}
