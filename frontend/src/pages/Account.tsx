import { Link, Navigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, naira } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { Order, Page } from '../lib/types'
import { Empty, ErrorState, Skeleton, StatusBadge } from '../components/ui'

export default function Account() {
  const { user, loading, logout } = useAuth()
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['orders', 'list'], enabled: !!user, queryFn: () => api<Page<Order>>('/orders/') })
  if (loading) return <div className="container-x py-10"><Skeleton className="h-64" /></div>
  if (!user) return <Navigate to="/login?next=/account" replace />
  return (
    <div className="container-x max-w-3xl py-10">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-4xl">My account</h1><p className="mt-1 text-sm text-muted">{user.name} · {user.email}</p></div>
        <div className="flex gap-2">{user.is_staff && <Link to="/admin" className="btn-outline">Admin dashboard</Link>}<button className="btn-ghost" onClick={() => logout()}>Sign out</button></div>
      </div>
      <h2 className="mt-10 text-2xl">Order history</h2>
      {isLoading ? <Skeleton className="mt-4 h-32" /> : isError ? <ErrorState onRetry={() => refetch()} />
        : !data?.results.length ? <Empty title="No orders yet" text="When you place an order it will appear here." action={<Link className="btn-primary" to="/shop">Start shopping</Link>} />
        : <ul className="mt-4 space-y-3">{data.results.map((o) => (
            <li key={o.reference}><Link to={`/orders/${o.reference}`} className="card flex flex-wrap items-center justify-between gap-3 p-4 hover:border-burgundy">
              <div><p className="font-medium tracking-wide">{o.reference}</p><p className="text-xs text-muted">{new Date(o.created_at).toLocaleDateString('en-NG', { dateStyle: 'medium' })} · {o.items.length} {o.items.length === 1 ? 'item' : 'items'}</p></div>
              <div className="flex flex-wrap items-center gap-2"><StatusBadge value={o.payment_tone} label={o.payment_status_display} /><StatusBadge value={o.fulfilment_status} label={o.fulfilment_status_display} />{o.dispatch_requested && <StatusBadge value={o.dispatch_status} label={o.dispatch_status_display} />}<span className="font-medium">{naira(o.total)}</span></div>
            </Link></li>))}</ul>}
    </div>
  )
}
