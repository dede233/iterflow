import { describe, expect, it } from 'vitest'
import { hashLoginRedirect, safeInternalRedirect } from './redirect'

describe('Hash login redirects', () => {
  it('preserves the complete business target and deployment base', () => {
    const path = '/requirements/42?tab=info&query=中文#section'
    expect(hashLoginRedirect(`#${path}`, '/app/')).toBe(`/app/#/login?redirect=${encodeURIComponent(path)}`)
    expect(safeInternalRedirect(path)).toBe(path)
  })
  it('does not redirect again from the Hash login page', () => {
    expect(hashLoginRedirect('#/login?redirect=%2Frequirements')).toBeNull()
  })
  it.each([undefined, [], 'https://evil.test', '//evil.test', '/\\evil.test', '/%2fevil.test', '/%252fevil.test', '/a\nfoo', 'javascript:alert(1)'])('rejects unsafe destinations: %s', value => {
    expect(safeInternalRedirect(value)).toBe('/')
  })
  it('keeps encoded external text inside an internal query rather than treating it as a destination', () => {
    expect(safeInternalRedirect('/requirements?query=https%3A%2F%2Fexample.test')).toBe('/requirements?query=https%3A%2F%2Fexample.test')
  })
})
