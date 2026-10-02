/** Inclusive calendar days become an exclusive next-local-day timestamp. */
export function releaseDateBounds(range: [string, string] | null): { released_from?: string; released_before?: string } {
  if (!range) return {}
  const localDay = (value: string) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error('日期格式无效')
    const [year, month, day] = value.split('-').map(Number) as [number, number, number]
    const date = new Date(0)
    date.setHours(0, 0, 0, 0)
    date.setFullYear(year, month - 1, day)
    if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) throw new Error('日期无效')
    return date
  }
  const from = localDay(range[0])
  const before = localDay(range[1])
  if (from > before) throw new Error('发布结束日期不能早于开始日期')
  before.setDate(before.getDate() + 1)
  return { released_from: from.toISOString(), released_before: before.toISOString() }
}
