import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, assetUrl, fieldError, naira } from './api'
import { jsonResponse } from '../test-utils'

afterEach(() => vi.restoreAllMocks())

describe('formatting helpers', () => {
  it('formats naira with thousands separators', () => { expect(naira(12500)).toBe('₦12,500'); expect(naira('8500.00')).toBe('₦8,500') })
  it('keeps relative storage URLs same-origin and leaves absolute CDN URLs alone', () => {
    expect(assetUrl('/media/products/a.png')).toBe('/media/products/a.png')
    expect(assetUrl('https://res.cloudinary.com/x/a.png')).toBe('https://res.cloudinary.com/x/a.png')
    expect(assetUrl(null)).toBe('')
  })
})

describe('api()', () => {
  it('turns a network failure into a friendly ApiError', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(api('/products/')).rejects.toMatchObject({ status: 0, code: 'network' })
  })
  it('surfaces field errors from the backend error shape', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ error: { code: 'validation_error', message: 'x', fields: { email: ['Already used'] } } }, 400))
    const e = await api('/auth/register/').catch((x) => x)
    expect(e).toBeInstanceOf(ApiError); expect(fieldError(e, 'email')).toBe('Already used')
  })
  it('refreshes the CSRF token and retries once on a CSRF failure', async () => {
    const f = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ csrfToken: 'old' }))                                   // initial token
      .mockResolvedValueOnce(jsonResponse({ error: { code: 'csrf_failed', message: 'CSRF Failed: please retry.' } }, 403))
      .mockResolvedValueOnce(jsonResponse({ csrfToken: 'new' }))                                   // refreshed token
      .mockResolvedValueOnce(jsonResponse({ ok: true }))
    expect(await api('/cart/', { method: 'PUT', body: { items: [] } })).toEqual({ ok: true })
    expect(f).toHaveBeenCalledTimes(4)
    expect((f.mock.calls[3][1] as RequestInit).headers).toMatchObject({ 'X-CSRFToken': 'new' })
  })
  it('announces an expired session so the app can sign the user out', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ error: { code: 'not_authenticated', message: 'Authentication credentials were not provided.' } }, 403))
    const heard = vi.fn(); window.addEventListener('ella:session-expired', heard)
    await api('/cart/').catch(() => {})
    expect(heard).toHaveBeenCalledTimes(1)
  })
})

describe('api() with a broken proxy', () => {
  it('treats an HTML 200 response (host served its own page) as an error, not as data', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('<!doctype html><html></html>', { status: 200, headers: { 'Content-Type': 'text/html' } }))
    await expect(api('/categories/')).rejects.toMatchObject({ status: 502, code: 'bad_response' })
  })
})
