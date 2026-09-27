// Receipt tokens are bearer secrets. They live in sessionStorage for the
// tab's lifetime and in the URL fragment (never sent to any server) when
// the guest bookmarks or downloads their status link.
const TOKEN_KEY = (ref: string): string => `jp:receipt:${ref}`
const FRESH_KEY = (ref: string): string => `jp:fresh:${ref}`

export function saveReceipt(ref: string, token: string, fresh: boolean): void {
  sessionStorage.setItem(TOKEN_KEY(ref), token)
  if (fresh) {
    sessionStorage.setItem(FRESH_KEY(ref), '1')
  }
}

export function loadToken(ref: string): string | null {
  return sessionStorage.getItem(TOKEN_KEY(ref))
}

export function isFresh(ref: string): boolean {
  return sessionStorage.getItem(FRESH_KEY(ref)) === '1'
}

export function markSaved(ref: string): void {
  sessionStorage.removeItem(FRESH_KEY(ref))
}

export function forgetToken(ref: string): void {
  sessionStorage.removeItem(TOKEN_KEY(ref))
  sessionStorage.removeItem(FRESH_KEY(ref))
}

export function statusLink(origin: string, ref: string, token: string): string {
  return `${origin}/cek/${encodeURIComponent(ref)}#token=${encodeURIComponent(token)}`
}

export function normalizeRef(value: string): string {
  const trimmed = value.trim().toUpperCase()
  return trimmed.startsWith('JP-') ? trimmed : `JP-${trimmed}`
}
