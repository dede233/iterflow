export interface StoredTokens {
  accessToken: string
  refreshToken: string
}

const ACCESS_TOKEN_KEY = 'iterflow.access_token'
const REFRESH_TOKEN_KEY = 'iterflow.refresh_token'

export function getStoredTokens(): StoredTokens | null {
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY)
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)
  return accessToken && refreshToken ? { accessToken, refreshToken } : null
}

export function setStoredTokens(tokens: StoredTokens): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken)
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken)
  // Clean up the short-lived Phase 0 key names, without affecting unrelated storage.
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

export function clearStoredTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}
