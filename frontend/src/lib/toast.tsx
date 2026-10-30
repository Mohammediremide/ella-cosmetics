import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { CheckCircle2, Info, XCircle } from 'lucide-react'

type Kind = 'success' | 'error' | 'info'
const Ctx = createContext<(msg: string, kind?: Kind) => void>(() => {})
export const useToast = () => useContext(Ctx)
const icons = { success: CheckCircle2, error: XCircle, info: Info }

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<{ id: number; msg: string; kind: Kind }[]>([])
  const push = useCallback((msg: string, kind: Kind = 'success') => {
    const id = Date.now() + Math.random()
    setItems((s) => [...s, { id, msg, kind }])
    setTimeout(() => setItems((s) => s.filter((t) => t.id !== id)), 4000)
  }, [])
  return (
    <Ctx.Provider value={push}>
      {children}
      {/* aria-live so screen readers announce feedback */}
      <div role="status" aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex flex-col items-center gap-2 px-4 sm:bottom-6">
        {items.map((t) => { const I = icons[t.kind]; return (
          <div key={t.id} className="pointer-events-auto flex max-w-md items-center gap-2.5 rounded-brand bg-charcoal px-4 py-3 text-sm text-white shadow-soft">
            <I size={18} className={t.kind === 'error' ? 'text-red-300' : 'text-blush'} aria-hidden /> {t.msg}
          </div>) })}
      </div>
    </Ctx.Provider>
  )
}
