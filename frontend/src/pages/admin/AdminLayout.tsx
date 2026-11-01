import { useState } from 'react'
import { Link, Navigate, NavLink, Outlet } from 'react-router-dom'
import { BadgeCheck, Film, LayoutDashboard, Users, Menu, Package, Receipt, Settings, Tags, X } from 'lucide-react'
import { useAuth } from '../../lib/auth'
import ThemeToggle from '../../components/ThemeToggle'
import { Skeleton } from '../../components/ui'

const items = [
  { to: '/admin', label: 'Overview', icon: LayoutDashboard, end: true }, { to: '/admin/payments', label: 'Payment Verification', icon: BadgeCheck },
  { to: '/admin/orders', label: 'Orders', icon: Receipt }, { to: '/admin/customers', label: 'Customers', icon: Users }, { to: '/admin/products', label: 'Products', icon: Package },
  { to: '/admin/sections', label: 'Manage Sections', icon: Tags }, { to: '/admin/slides', label: 'Homepage Slideshow', icon: Film }, { to: '/admin/settings', label: 'Settings', icon: Settings },
]

export default function AdminLayout() {
  const { user, loading, logout } = useAuth()
  const [open, setOpen] = useState(false)
  if (loading) return <div className="p-8"><Skeleton className="h-64" /></div>
  // UX guard only. The API enforces staff-only access on every admin endpoint.
  if (!user) return <Navigate to="/login?next=/admin" replace />
  if (!user.is_staff) return (
    <div className="mx-auto max-w-md px-6 py-24 text-center"><h1 className="text-4xl text-burgundy">Staff only</h1><p className="mt-3 text-sm text-muted">Your account doesn’t have access to the admin dashboard.</p><Link to="/" className="btn-primary mt-6">Back to the store</Link></div>
  )
  const nav = (
    <nav className="flex flex-col gap-1" aria-label="Admin" onClick={() => setOpen(false)}>
      {items.map(({ to, label, icon: I, end }) => (
        <NavLink key={to} to={to} end={end} className={({ isActive }) => `flex min-h-[44px] items-center gap-3 rounded-brand px-3 text-sm ${isActive ? 'bg-burgundy text-white' : 'hover:bg-blush/60'}`}><I size={18} aria-hidden /> {label}</NavLink>))}
    </nav>
  )
  return (
    <div className="min-h-screen bg-ivory md:flex">
      <aside className="hidden w-60 shrink-0 border-r border-taupe/20 bg-surface p-4 md:block">
        <p className="mb-6 px-3 font-serif text-xl text-burgundy">Ella Admin</p>{nav}
        <div className="mt-8 border-t border-taupe/20 pt-4 text-sm"><Link className="block px-3 py-2 hover:text-burgundy" to="/">View storefront</Link><ThemeToggle withLabel className="w-full !justify-start" /><button className="px-3 py-2 hover:text-burgundy" onClick={() => logout()}>Sign out</button></div>
      </aside>
      <div className="flex-1 min-w-0">
        <header className="flex h-14 items-center justify-between border-b border-taupe/20 bg-surface px-4 md:hidden">
          <button className="btn-ghost -ml-3 px-3" aria-label="Open admin menu" onClick={() => setOpen(true)}><Menu size={22} /></button><span className="font-serif text-lg text-burgundy">Ella Admin</span><ThemeToggle className="-mr-3" />
        </header>
        {open && <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label="Admin menu"><div className="absolute inset-0 bg-charcoal/50" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-72 bg-surface p-4"><button className="btn-ghost mb-4 px-3" aria-label="Close menu" onClick={() => setOpen(false)}><X size={22} /></button>{nav}
            <Link to="/" className="mt-6 block px-3 py-2 text-sm">View storefront</Link></div></div>}
        <main className="mx-auto max-w-6xl p-4 sm:p-8"><Outlet /></main>
      </div>
    </div>
  )
}
