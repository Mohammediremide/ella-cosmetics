import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { api } from './api'
import { useAuth } from './auth'
import { useToast } from './toast'
import type { CartData } from './types'

// Guests keep ONLY {product_id, quantity} locally; prices always come from the server.
// Signed-in customers use the server cart; a guest cart is merged on login.
type Pair = { product_id: number; quantity: number }
const KEY = 'ella_guest_cart'
const readLocal = (): Pair[] => { try { return JSON.parse(localStorage.getItem(KEY) || '[]') } catch { return [] } }
const writeLocal = (p: Pair[]) => { try { localStorage.setItem(KEY, JSON.stringify(p)) } catch { /* storage unavailable */ } }
const empty: CartData = { items: [], subtotal: 0, adjusted: false }

interface CartCtx {
  cart: CartData; count: number; loading: boolean
  setQuantity: (productId: number, qty: number) => Promise<void>
  add: (productId: number, qty?: number) => Promise<void>
  remove: (productId: number) => Promise<void>
  clearLocal: () => void; refresh: () => Promise<void>
}
const Ctx = createContext<CartCtx>(null!)
export const useCart = () => useContext(Ctx)

export function CartProvider({ children }: { children: ReactNode }) {
  const { user, loading: authLoading } = useAuth()
  const toast = useToast()
  const [cart, setCart] = useState<CartData>(empty)
  const [loading, setLoading] = useState(true)
  const lastUser = useRef<number | null | undefined>(undefined)

  const apply = useCallback((d: CartData, signedIn: boolean) => {
    setCart(d)
    if (!signedIn) writeLocal(d.items.map((l) => ({ product_id: l.product_id, quantity: l.quantity })))
    if (d.adjusted) toast('Some cart items were updated to match current availability.', 'info')
  }, [toast])

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      if (user) apply(await api<CartData>('/cart/'), true)
      else { const l = readLocal(); apply(l.length ? await api<CartData>('/cart/validate/', { method: 'POST', body: { items: l } }) : empty, false) }
    } catch { /* keep current cart */ } finally { setLoading(false) }
  }, [user, apply])

  useEffect(() => {
    if (authLoading) return
    const uid = user?.id ?? null
    if (lastUser.current === uid) return
    const wasGuest = lastUser.current === null || lastUser.current === undefined
    lastUser.current = uid
    ;(async () => {
      if (user && wasGuest && readLocal().length) {
        setLoading(true)
        try { apply(await api<CartData>('/cart/merge/', { method: 'POST', body: { items: readLocal() } }), true); localStorage.removeItem(KEY) } finally { setLoading(false) }
      } else await refresh()
    })()
  }, [user, authLoading, refresh, apply])

  const push = async (pairs: Pair[]) => {
    apply(user ? await api<CartData>('/cart/', { method: 'PUT', body: { items: pairs } })
               : await api<CartData>('/cart/validate/', { method: 'POST', body: { items: pairs } }), !!user)
  }
  const pairs = () => cart.items.map((l) => ({ product_id: l.product_id, quantity: l.quantity }))
  const setQuantity = async (id: number, qty: number) => {
    const next = pairs().filter((p) => p.product_id !== id)
    if (qty > 0) next.push({ product_id: id, quantity: qty })
    await push(next)
  }
  const value: CartCtx = {
    cart, loading, count: cart.items.reduce((n, l) => n + l.quantity, 0), setQuantity,
    add: async (id, qty = 1) => setQuantity(id, (cart.items.find((l) => l.product_id === id)?.quantity ?? 0) + qty),
    remove: (id) => setQuantity(id, 0), refresh,
    clearLocal: () => { localStorage.removeItem(KEY); setCart(empty) },
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
