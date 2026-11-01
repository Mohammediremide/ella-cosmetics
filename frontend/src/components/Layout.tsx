import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, Menu, Search, ShoppingBag, User as UserIcon, X } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useCart } from '../lib/cart'
import type { Category, PublicSettings } from '../lib/types'
import ThemeToggle from './ThemeToggle'

export const usePublicSettings = () => useQuery({ queryKey: ['settings'], staleTime: 60_000, queryFn: () => api<PublicSettings>('/settings/') })
// Sections come from the backend (active only, in the order the admin chose): nothing is hardcoded here
export const useCategories = () => useQuery({ queryKey: ['categories'], staleTime: 60_000, queryFn: () => api<Category[]>('/categories/') })

function CategoryMenu({ cats }: { cats: Category[] }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const out = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false)
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', out); document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', out); document.removeEventListener('keydown', esc) }
  }, [open])
  return (
    <div className="relative" ref={ref}>
      <button className="flex items-center gap-1 py-2 text-sm hover:text-burgundy" aria-expanded={open} aria-haspopup="true" onClick={() => setOpen((v) => !v)}>
        Shop by Category <ChevronDown size={14} aria-hidden className={open ? 'rotate-180 transition-transform' : 'transition-transform'} />
      </button>
      {open && (
        <ul className="card absolute left-0 top-full z-50 mt-2 w-60 py-2" onClick={() => setOpen(false)}>
          <li><Link className="block px-4 py-2.5 text-sm font-medium hover:bg-blush/50" to="/shop">All Products</Link></li>
          {cats.map((c) => <li key={c.id}><Link className="block px-4 py-2.5 text-sm hover:bg-blush/50" to={`/shop?category=${c.slug}`}>{c.name}</Link></li>)}
        </ul>
      )}
    </div>
  )
}

export default function Layout() {
  const { data: s, isError: serverDown } = usePublicSettings()
  const { data: cats = [] } = useCategories()
  const { user, logout } = useAuth()
  const { count } = useCart()
  const nav = useNavigate()
  const loc = useLocation()
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [searching, setSearching] = useState(false)
  const last = useRef('')
  const link = ({ isActive }: { isActive: boolean }) => `py-2 text-sm hover:text-burgundy ${isActive ? 'text-burgundy font-medium' : ''}`
  const search = (e: React.FormEvent) => { e.preventDefault(); nav(`/shop?search=${encodeURIComponent(q)}`); setSearching(false); setOpen(false) }
  const wa = s?.whatsapp_number

  // Privacy-friendly visit counting (no cookies; the server ignores staff, bots and admin pages)
  useEffect(() => {
    window.scrollTo({ top: 0 })
    if (last.current === loc.pathname || user?.is_staff) return
    last.current = loc.pathname
    api('/analytics/visit/', { method: 'POST', body: { path: loc.pathname } }).catch(() => {})
  }, [loc.pathname, user?.is_staff])

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-surface focus:p-3">Skip to content</a>
      {serverDown && <div role="alert" className="bg-amber-100 px-4 py-2 text-center text-sm text-amber-900">We’re having trouble reaching the store server. Please refresh in a minute.</div>}
      {s?.announcement && <div className="bg-burgundy px-4 py-2 text-center text-xs tracking-wide text-white">{s.announcement}</div>}
      <header className="sticky top-0 z-40 border-b border-taupe/20 bg-ivory/95 backdrop-blur">
        <div className="container-x flex h-16 items-center justify-between gap-4">
          <button className="btn-ghost -ml-3 px-3 md:hidden" aria-label="Open menu" onClick={() => setOpen(true)}><Menu size={22} /></button>
          <Link to="/" className="font-serif text-2xl text-burgundy">{s?.store_name ?? 'Ella Cosmetics'}</Link>
          <nav className="hidden items-center gap-7 md:flex" aria-label="Main">
            <NavLink to="/" end className={link}>Home</NavLink>
            <NavLink to="/shop" end className={link}>All Products</NavLink>
            {cats.length > 0 && <CategoryMenu cats={cats} />}
          </nav>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <button className="btn-ghost px-3" aria-label="Search" aria-expanded={searching} onClick={() => setSearching((v) => !v)}><Search size={20} /></button>
            <Link to={user ? '/account' : '/login'} className="btn-ghost px-3" aria-label={user ? 'Account' : 'Sign in'}><UserIcon size={20} /></Link>
            <Link to="/cart" className="btn-ghost relative px-3" aria-label={`Cart, ${count} items`}>
              <ShoppingBag size={20} />
              {count > 0 && <span className="absolute right-0.5 top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-burgundy px-1 text-[11px] font-semibold text-white">{count}</span>}
            </Link>
          </div>
        </div>
        {searching && (
          <form onSubmit={search} className="container-x pb-3" role="search">
            <input autoFocus className="input" type="search" placeholder="Search products" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search products" />
          </form>
        )}
      </header>

      {open && (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="absolute inset-0 bg-charcoal/50" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-80 max-w-[85%] flex-col overflow-y-auto bg-ivory p-5">
            <button className="btn-ghost -mr-3 self-end px-3" aria-label="Close menu" onClick={() => setOpen(false)}><X size={22} /></button>
            <form onSubmit={search} className="mt-2"><input className="input" type="search" placeholder="Search products" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search products" /></form>
            <nav className="mt-4 flex flex-col" onClick={() => setOpen(false)} aria-label="Mobile">
              <Link className="py-3 font-serif text-2xl" to="/">Home</Link>
              <p className="mt-3 text-xs font-medium uppercase tracking-[0.2em] text-muted">Shop by Category</p>
              <Link className="py-3 font-serif text-2xl" to="/shop">All Products</Link>
              {cats.map((c) => <Link key={c.id} className="py-2.5 pl-3 text-lg" to={`/shop?category=${c.slug}`}>{c.name}</Link>)}
              <ThemeToggle withLabel className="mt-4 !justify-start !px-0" />
              <Link className="py-3 text-base" to={user ? '/account' : '/login'}>{user ? 'My account' : 'Sign in'}</Link>
              {user?.is_staff && <Link className="py-3 text-base" to="/admin">Admin dashboard</Link>}
              {user && <button className="py-3 text-left text-base" onClick={() => logout()}>Sign out</button>}
            </nav>
          </div>
        </div>
      )}

      <main id="main" className="flex-1"><Outlet /></main>

      <footer className="mt-20 bg-charcoal pb-20 text-cream md:pb-0">
        <div className="container-x grid gap-10 py-14 md:grid-cols-3">
          <div><p className="font-serif text-2xl">{s?.store_name ?? 'Ella Cosmetics'}</p><p className="mt-3 max-w-xs text-sm text-cream/75">Beauty essentials for every day, every mood, and every version of you.</p></div>
          <nav aria-label="Footer" className="flex flex-col gap-2 text-sm"><p className="font-medium">Shop by Category</p><Link className="text-cream/75 hover:text-white" to="/shop">All Products</Link>{cats.map((c) => <Link key={c.id} className="text-cream/75 hover:text-white" to={`/shop?category=${c.slug}`}>{c.name}</Link>)}<Link className="mt-2" to="/account">My account</Link></nav>
          <div className="flex flex-col gap-2 text-sm">
            <p className="font-medium">Contact</p>
            {wa && <a className="text-cream/75 hover:text-white" href={`https://wa.me/${wa}`} target="_blank" rel="noreferrer">Chat on WhatsApp</a>}
            {s?.contact_email && <a className="text-cream/75" href={`mailto:${s.contact_email}`}>{s.contact_email}</a>}
            {s?.contact_phone && <span className="text-cream/75">{s.contact_phone}</span>}
            {s?.instagram_url && <a className="text-cream/75" href={s.instagram_url} target="_blank" rel="noreferrer">Instagram</a>}
            {!wa && !s?.contact_email && !s?.contact_phone && <span className="text-cream/60">Contact details coming soon.</span>}
            <div className="mt-2 flex gap-4 text-cream/75"><Link to="/privacy">Privacy</Link><Link to="/terms">Terms</Link></div>
          </div>
        </div>
        <p className="border-t border-white/10 py-5 text-center text-xs text-cream/60">© {new Date().getFullYear()} {s?.store_name ?? 'Ella Cosmetics'}. All rights reserved.</p>
      </footer>

      {count > 0 && <Link to="/cart" className="btn-primary fixed inset-x-4 bottom-4 z-30 shadow-soft md:hidden">View cart · {count} {count === 1 ? 'item' : 'items'}</Link>}
    </div>
  )
}
