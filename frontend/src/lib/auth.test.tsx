import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth } from './auth'
import { jsonResponse, renderAt } from '../test-utils'

afterEach(() => vi.restoreAllMocks())

function Probe() {
  const { user, logout } = useAuth()
  return <div><p>{user ? `signed in as ${user.name}` : 'signed out'}</p><button onClick={() => logout()}>Sign out</button></div>
}

describe('AuthProvider', () => {
  it('Sign out updates the screen immediately', async () => {
    let signedIn = true
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
      const u = String(url)
      if (u.includes('/auth/csrf/')) return jsonResponse({ csrfToken: 't' })
      if (u.includes('/auth/logout/')) { signedIn = false; return new Response(null, { status: 204 }) }
      if (u.includes('/auth/me/')) return jsonResponse(signedIn ? { id: 1, name: 'Ada', email: 'a@x.com', phone: '', is_staff: false } : { authenticated: false })
      return jsonResponse({}, init?.method === 'GET' ? 200 : 200)
    })
    renderAt(<AuthProvider><Probe /></AuthProvider>)
    await screen.findByText('signed in as Ada')
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    await waitFor(() => expect(screen.getByText('signed out')).toBeTruthy())
  })
})
