// Fetch wrapper: HttpOnly cookie sessions + CSRF header. No tokens or passwords ever touch localStorage.
// VITE_API_BASE_URL is empty by default (same-origin: Vite proxy in dev, Vercel rewrite in production).
// Set it only to call the API host directly (then the backend needs COOKIE_SAMESITE=None).
const BASE = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public fields: Record<string, string[] | string> = {}) {
    super(message)
  }
}

/** Storage URLs are relative ('/media/..') locally and absolute (https://res.cloudinary.com/..) on Cloudinary. */
export const assetUrl = (u?: string | null) => (!u ? '' : /^(https?:|data:)/.test(u) ? u : `${BASE}${u}`)

let csrfToken = ''
export async function ensureCsrf(force = false) {
  if (csrfToken && !force) return
  const r = await fetch(`${BASE}/api/auth/csrf/`, { credentials: 'include' })
  csrfToken = (await r.json()).csrfToken ?? ''
}

type Opts = { method?: string; body?: any; form?: FormData; headers?: Record<string, string> }

export async function api<T = any>(path: string, opts: Opts = {}, retried = false): Promise<T> {
  const method = opts.method ?? 'GET'
  const headers: Record<string, string> = { ...opts.headers }
  try {
    if (method !== 'GET') { await ensureCsrf(); headers['X-CSRFToken'] = csrfToken }
    let body: BodyInit | undefined
    if (opts.form) body = opts.form
    else if (opts.body !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(opts.body) }
    var res = await fetch(`${BASE}/api${path}`, { method, headers, body, credentials: 'include' })
  } catch {
    throw new ApiError(0, 'network', 'We couldn’t reach the store. Check your internet connection and try again.')
  }
  if (res.status === 204) return undefined as T
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const e = data?.error ?? {}
    // Stale CSRF token (e.g. after login/logout rotation): fetch a fresh one and retry once
    if (res.status === 403 && /CSRF/i.test(e.message ?? '') && !retried) { await ensureCsrf(true); return api<T>(path, opts, true) }
    // Session expired mid-visit: tell the app so it can sign the user out gracefully
    if ([401, 403].includes(res.status) && e.code === 'not_authenticated' && !path.startsWith('/auth/')) window.dispatchEvent(new Event('ella:session-expired'))
    const f = e.fields ?? {}
    const msg = (Array.isArray(f.detail) ? f.detail[0] : f.detail) || e.message || 'Something went wrong. Please try again.'
    throw new ApiError(res.status, e.code ?? 'error', msg, f)
  }
  return data as T
}

export const naira = (v: number | string) => '₦' + Number(v).toLocaleString('en-NG', { maximumFractionDigits: 2 })
export const fieldError = (e: unknown, name: string): string | undefined => {
  if (!(e instanceof ApiError)) return
  const v = e.fields[name]
  return Array.isArray(v) ? v[0] : (v as string | undefined)
}
export const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString('en-NG', { dateStyle: 'medium', timeStyle: 'short' }) : '—')
