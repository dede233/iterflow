// New pictures stay in the editor until the requirement write succeeds.
const pending = new Map<string, File>()
export function rememberImage(file: File) {
  const key = 'local-' + crypto.randomUUID()
  pending.set(key, file)
  return key
}
export function forgetImage(key: string) { pending.delete(key) }
export function pendingImage(key: string) { return pending.get(key) }
export async function withDescriptionImages<T extends { description?: string | null; description_format?: string }>(payload: T) {
  if (payload.description_format !== 'HTML' || !payload.description?.includes('data-file-id="local-')) return payload
  const parsed = document.createElement('template')
  parsed.innerHTML = payload.description
  const refs = new Set(Array.from(parsed.content.querySelectorAll('img[data-file-id^="local-"]'), img => img.getAttribute('data-file-id')!))
  const images: Record<string, string> = {}
  let total = 0
  for (const key of refs) {
    const file = pending.get(key)
    if (!file) throw new Error('请重新插入未载入的图片')
    total += file.size
    if (total > 8 * 1024 * 1024) throw new Error('本次新增图片总计不能超过 8 MiB')
    images[key] = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result))
      reader.onerror = () => reject(new Error('图片读取失败'))
      reader.readAsDataURL(file)
    })
  }
  return { ...payload, description_images: images }
}
