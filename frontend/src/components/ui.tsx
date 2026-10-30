import { useEffect, useRef, type ReactNode } from 'react'
import { AlertTriangle, PackageSearch } from 'lucide-react'
import { assetUrl } from '../lib/api'
import type { Product } from '../lib/types'

export const PUBLIC_STATUS: Record<Product['stock_status'], { label: string; cls: string }> = {
  in_stock: { label: 'In stock', cls: 'bg-emerald-50 text-emerald-800' },
  low_stock: { label: 'Low stock', cls: 'bg-amber-50 text-amber-800' },
  out_of_stock: { label: 'Out of stock', cls: 'bg-stone-100 text-stone-600' },
}
export function StockBadge({ status }: { status: Product['stock_status'] }) {
  const s = PUBLIC_STATUS[status]
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${s.cls}`}>{s.label}</span>
}

const TONES: Record<string, string> = {
  awaiting_payment: 'bg-stone-100 text-stone-700', pending_verification: 'bg-amber-50 text-amber-900', verified: 'bg-emerald-50 text-emerald-800', rejected: 'bg-red-50 text-red-800',
  pending: 'bg-stone-100 text-stone-700', processing: 'bg-blue-50 text-blue-800', dispatched: 'bg-indigo-50 text-indigo-800',
  delivered: 'bg-emerald-50 text-emerald-800', cancelled: 'bg-red-50 text-red-800',
}
export const StatusBadge = ({ value, label }: { value: string; label: string }) => (
  <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${TONES[value] ?? 'bg-stone-100'}`}>{label}</span>
)

/** Fixed aspect ratio => no layout shift; branded placeholder when a product has no photo yet. */
export function Img({ src, alt, ratio = 'aspect-[4/5]', eager }: { src?: string | null; alt: string; ratio?: string; eager?: boolean }) {
  return src ? (
    <img src={assetUrl(src)} alt={alt} loading={eager ? 'eager' : 'lazy'} decoding="async" className={`${ratio} w-full object-cover`} />
  ) : (
    <div className={`${ratio} flex w-full items-center justify-center bg-blush/60 font-serif text-4xl text-burgundy/40`} role="img" aria-label={alt}>E</div>
  )
}

export const Skeleton = ({ className = '' }: { className?: string }) => <div className={`animate-pulse rounded-brand bg-blush/50 ${className}`} aria-hidden />

export function Empty({ title, text, action }: { title: string; text?: string; action?: ReactNode }) {
  return (
    <div className="mx-auto flex max-w-sm flex-col items-center py-16 text-center">
      <PackageSearch className="mb-4 text-rose" size={40} aria-hidden />
      <h2 className="text-2xl">{title}</h2>
      {text && <p className="mt-2 text-sm text-muted">{text}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}
/** Section / empty-catalogue placeholder: intentional, not a fake product. */
export function EmptySection({ name, onAll }: { name?: string; onAll?: () => void }) {
  return (
    <div className="mx-auto max-w-md rounded-brand border border-dashed border-rose/60 bg-blush/30 px-6 py-14 text-center">
      <p className="font-serif text-3xl text-burgundy">{name ? `${name} is coming soon` : 'Nothing here yet'}</p>
      <p className="mt-3 text-sm text-muted">{name ? 'We’re preparing this section. Please check back soon, or browse everything else in the shop.' : 'New products will appear here as soon as they’re added.'}</p>
      {onAll && <button className="btn-primary mt-6" onClick={onAll}>View all products</button>}
    </div>
  )
}

export function ErrorState({ message = 'We couldn’t load this. Please try again.', onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="mx-auto flex max-w-sm flex-col items-center py-16 text-center">
      <AlertTriangle className="mb-3 text-burgundy" size={36} aria-hidden />
      <p className="text-sm">{message}</p>
      {onRetry && <button className="btn-outline mt-4" onClick={onRetry}>Try again</button>}
    </div>
  )
}

/** Accessible modal: focus trap-lite, Esc to close, restores focus. */
export function Modal({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  const closeRef = useRef(onClose)
  closeRef.current = onClose  // always call the latest handler without re-running the focus effect
  useEffect(() => {
    if (!open) return
    const prev = document.activeElement as HTMLElement | null
    // focus the first field if there is one, otherwise the dialog itself; only when it OPENS (not on every keystroke)
    const first = ref.current?.querySelector<HTMLElement>('input:not([type=hidden]), textarea, select')
    ;(first ?? ref.current)?.focus()
    const k = (e: KeyboardEvent) => e.key === 'Escape' && closeRef.current()
    document.addEventListener('keydown', k)
    return () => { document.removeEventListener('keydown', k); prev?.focus() }
  }, [open])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-charcoal/50 p-4 sm:items-center" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title} className="card w-full max-w-md p-6 outline-none">
        <h2 className="text-2xl">{title}</h2>
        <div className="mt-3">{children}</div>
      </div>
    </div>
  )
}

export function Field({ label, error, children, htmlFor }: { label: string; error?: string; children: ReactNode; htmlFor: string }) {
  return (
    <div>
      <label className="label" htmlFor={htmlFor}>{label}</label>
      {children}
      {error && <p className="field-error" role="alert">{error}</p>}
    </div>
  )
}

export function Pager({ page, count, size = 12, onPage }: { page: number; count: number; size?: number; onPage: (n: number) => void }) {
  const pages = Math.max(1, Math.ceil(count / size))
  if (pages <= 1) return null
  return (
    <nav className="flex items-center justify-center gap-4 p-4" aria-label="Pagination">
      <button className="btn-outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
      <span className="text-sm text-muted">Page {page} of {pages}</span>
      <button className="btn-outline" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
    </nav>
  )
}
