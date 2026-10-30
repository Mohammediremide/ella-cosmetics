import { createContext, useContext, useEffect, type ReactNode } from 'react'
import { useToast } from './toast'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError, ensureCsrf } from './api'
import type { User } from './types'

interface AuthCtx {
  user: User | null; loading: boolean
  login: (email: string, password: string) => Promise<User>
  register: (d: { name: string; email: string; password: string; phone?: string }) => Promise<User>
  logout: () => Promise<void>
}
const Ctx = createContext<AuthCtx>(null!)
export const useAuth = () => useContext(Ctx)

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const toast = useToast()
  const { data, isLoading } = useQuery({
    queryKey: ['me'], staleTime: 5 * 60_000, retry: false,
    queryFn: async () => { try { const u = await api<User & { authenticated?: boolean }>('/auth/me/'); return u?.id ? u : null } catch (e) { if (e instanceof ApiError && [401, 403].includes(e.status)) return null; throw e } },
  })
  useEffect(() => {
    const h = () => { qc.setQueryData(['me'], null); toast('Your session has expired. Please sign in again.', 'info') }
    window.addEventListener('ella:session-expired', h)
    return () => window.removeEventListener('ella:session-expired', h)
  }, [qc, toast])
  // login/logout rotate Django's CSRF token: fetch the new one BEFORE the app reacts to the new user
  const set = async (u: User | null) => { await ensureCsrf(true).catch(() => {}); qc.setQueryData(['me'], u); qc.invalidateQueries({ queryKey: ['orders'] }) }
  const value: AuthCtx = {
    user: data ?? null, loading: isLoading,
    login: async (email, password) => { const u = await api<User>('/auth/login/', { method: 'POST', body: { email, password } }); await set(u); return u },
    register: async (d) => { const u = await api<User>('/auth/register/', { method: 'POST', body: d }); await set(u); return u },
    logout: async () => {
      await api('/auth/logout/', { method: 'POST' })
      await ensureCsrf(true).catch(() => {})
      qc.setQueryData(['me'], null)  // update the SAME query the app is watching (qc.clear() detached it, so the screen never changed)
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== 'me' })  // forget the previous user's orders / admin data
    },
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
