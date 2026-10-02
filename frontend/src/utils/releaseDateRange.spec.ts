import { afterEach, expect, it, vi } from 'vitest'
import { releaseDateBounds } from './releaseDateRange'
afterEach(() => vi.unstubAllEnvs())
it('omits cleared dates and rejects reversed or invalid calendar input', () => {
  expect(releaseDateBounds(null)).toEqual({})
  expect(() => releaseDateBounds(['2026-10-02', '2026-10-01'])).toThrow('不能早于')
  expect(() => releaseDateBounds(['2026-02-30', '2026-03-01'])).toThrow('日期无效')
})
it('converts local inclusive days into offset-aware UTC bounds', () => {
  vi.stubEnv('TZ', 'Asia/Shanghai')
  expect(releaseDateBounds(['2026-10-01', '2026-10-02'])).toEqual({ released_from: '2026-09-30T16:00:00.000Z', released_before: '2026-10-02T16:00:00.000Z' })
})
it.each([
  ['2026-03-08', '2026-03-08T05:00:00.000Z', '2026-03-09T04:00:00.000Z', 23],
  ['2026-11-01', '2026-11-01T04:00:00.000Z', '2026-11-02T05:00:00.000Z', 25],
])('uses the next local midnight across DST: %s', (day, from, before, hours) => {
  vi.stubEnv('TZ', 'America/New_York')
  const bounds = releaseDateBounds([day, day])
  expect(bounds).toEqual({ released_from: from, released_before: before })
  expect((Date.parse(bounds.released_before!) - Date.parse(bounds.released_from!)) / 3600000).toBe(hours)
})
