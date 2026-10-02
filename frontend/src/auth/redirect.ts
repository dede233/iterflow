/** Only local Vue Router paths may be used as a post-login destination. */
export function safeInternalRedirect(value: unknown): string {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return '/'
  const path = value.split(/[?#]/, 1)[0]!
  if (/[\\\u0000-\u0020\u007f]/.test(value) || /%(?:2f|5c|00|0a|0d|25)/i.test(path)) return '/'
  return value
}

export function hashLoginRedirect(hash: string, base = import.meta.env.BASE_URL): string | null {
  const target = safeInternalRedirect(hash.startsWith('#') ? hash.slice(1) : '/')
  if (target.split(/[?#]/, 1)[0] === '/login') return null
  return `${base}#/login?redirect=${encodeURIComponent(target)}`
}
