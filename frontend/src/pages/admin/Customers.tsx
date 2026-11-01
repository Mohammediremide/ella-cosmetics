import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Mail, MessageCircle, Phone } from 'lucide-react'
import { api, naira, when } from '../../lib/api'
import { StatusBadge, Empty, ErrorState, Pager, Skeleton } from '../../components/ui'
import type { Page } from '../../lib/types'

interface CustomerRow {
  id: number; name: string; email: string; phone: string; role: 'customer' | 'staff'; is_active: boolean
  date_joined: string; last_login: string | null; order_count: number; verified_spend: string; last_order_at: string | null
}
interface CustomerOrder { reference: string; created_at: string; total: string; delivery_method: string; payment_status: string; payment_status_display: string; fulfilment_status: string; fulfilment_status_display: string; items: string[] }
interface CustomerDetail extends CustomerRow {
  orders: CustomerOrder[]; addresses: { address: string; last_used: string }[]; other_phones: string[]
  cart: { name: string; quantity: number; unit_price: string }[]; whatsapp_url: string
}

const Row = ({ k, children }: { k: string; children: React.ReactNode }) => <div className="flex flex-wrap justify-between gap-x-4 py-1.5 text-sm"><dt className="text-muted">{k}</dt><dd className="text-right font-medium">{children}</dd></div>

function Detail({ id, onClose }: { id: number; onClose: () => void }) {
  const { data: c, isLoading, isError } = useQuery({ queryKey: ['admin', 'customer', id], queryFn: () => api<CustomerDetail>(`/admin/customers/${id}/`) })
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-charcoal/40" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside role="dialog" aria-modal="true" aria-label="Customer details" className="h-full w-full max-w-lg overflow-y-auto bg-ivory p-6">
        <div className="flex items-start justify-between gap-3"><h2 className="text-3xl">{c?.name ?? 'Customer'}</h2><button className="btn-ghost" onClick={onClose}>Close</button></div>
        {isLoading ? <Skeleton className="mt-6 h-64" /> : isError || !c ? <ErrorState message="Couldn’t load this customer." /> : (
          <>
            <div className="mt-2 flex flex-wrap gap-2"><StatusBadge value={c.role === 'staff' ? 'processing' : 'pending'} label={c.role === 'staff' ? 'Staff' : 'Customer'} />{!c.is_active && <StatusBadge value="cancelled" label="Account disabled" />}</div>
            <div className="mt-4 flex flex-wrap gap-2">
              {c.whatsapp_url && <a className="btn-outline" href={c.whatsapp_url} target="_blank" rel="noreferrer"><MessageCircle size={16} aria-hidden /> WhatsApp</a>}
              {c.phone && <a className="btn-outline" href={`tel:${c.phone}`}><Phone size={16} aria-hidden /> Call</a>}
              <a className="btn-outline" href={`mailto:${c.email}`}><Mail size={16} aria-hidden /> Email</a>
            </div>
            <section className="card mt-5 p-4"><h3 className="font-sans text-sm font-semibold">Account</h3>
              <dl className="mt-1 divide-y divide-taupe/15">
                <Row k="Email"><span className="break-all">{c.email}</span></Row><Row k="Phone">{c.phone || '—'}</Row>
                <Row k="Joined">{when(c.date_joined)}</Row><Row k="Last sign-in">{when(c.last_login)}</Row>
                <Row k="Orders">{c.order_count}</Row><Row k="Verified spend">{naira(c.verified_spend)}</Row><Row k="Last order">{when(c.last_order_at)}</Row>
              </dl>
              <p className="mt-2 text-xs text-muted">Passwords are never shown. They are stored scrambled and nobody, including you, can read them.</p>
            </section>
            {c.addresses.length > 0 && <section className="card mt-4 p-4"><h3 className="font-sans text-sm font-semibold">Delivery addresses used</h3>
              <ul className="mt-2 space-y-2 text-sm">{c.addresses.map((a) => <li key={a.address}>{a.address}<span className="block text-xs text-muted">last used {when(a.last_used)}</span></li>)}</ul></section>}
            {c.other_phones.length > 0 && <section className="card mt-4 p-4"><h3 className="font-sans text-sm font-semibold">Other phone numbers used at checkout</h3><p className="mt-1 text-sm">{c.other_phones.join(', ')}</p></section>}
            <section className="card mt-4 p-4"><h3 className="font-sans text-sm font-semibold">Orders ({c.orders.length})</h3>
              {!c.orders.length ? <p className="mt-2 text-sm text-muted">No orders yet.</p> : (
                <ul className="mt-2 divide-y divide-taupe/15">{c.orders.map((o) => (
                  <li key={o.reference} className="py-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{o.reference}</span><span>{naira(o.total)}</span></div>
                    <p className="text-xs text-muted">{when(o.created_at)} · {o.delivery_method}</p>
                    <p className="mt-1 text-xs">{o.items.join(', ')}</p>
                    <div className="mt-1.5 flex flex-wrap gap-1.5"><StatusBadge value={o.payment_status} label={o.payment_status_display} /><StatusBadge value={o.fulfilment_status} label={o.fulfilment_status_display} /></div>
                  </li>))}</ul>)}
            </section>
            {c.cart.length > 0 && <section className="card mt-4 p-4"><h3 className="font-sans text-sm font-semibold">Currently in their cart</h3>
              <ul className="mt-2 space-y-1 text-sm">{c.cart.map((i) => <li key={i.name} className="flex justify-between gap-3"><span>{i.name} × {i.quantity}</span><span className="text-muted">{naira(i.unit_price)} each</span></li>)}</ul></section>}
          </>
        )}
      </aside>
    </div>
  )
}

export default function Customers() {
  const [search, setSearch] = useState(''), [role, setRole] = useState(''), [sort, setSort] = useState('-date_joined'), [page, setPage] = useState(1)
  const [open, setOpen] = useState<number | null>(null)
  const qs = new URLSearchParams({ search, page: String(page), ordering: sort, ...(role && { role }) })
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ['admin', 'customers', qs.toString()], queryFn: () => api<Page<CustomerRow>>(`/admin/customers/?${qs}`) })
  return (
    <div>
      <h1 className="text-4xl">Customers</h1>
      <p className="mt-1 max-w-xl text-sm text-muted">Everyone with an account, with their contact details, orders and delivery addresses. Passwords are never visible. Treat this information as private.</p>
      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <input className="input" type="search" placeholder="Search name, email or phone" aria-label="Search customers" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }} />
        <select className="input" aria-label="Account type" value={role} onChange={(e) => { setRole(e.target.value); setPage(1) }}><option value="">Customers and staff</option><option value="customer">Customers only</option><option value="staff">Staff only</option></select>
        <select className="input" aria-label="Sort" value={sort} onChange={(e) => { setSort(e.target.value); setPage(1) }}>
          <option value="-date_joined">Newest first</option><option value="-verified_spend">Highest spend</option><option value="-order_count">Most orders</option><option value="-last_login">Recently active</option><option value="name">Name A–Z</option></select>
      </div>
      <div className="card mt-4 overflow-x-auto">
        {isError ? <ErrorState onRetry={() => refetch()} /> : isLoading ? <Skeleton className="h-48" /> : !data?.results.length ? <Empty title="No customers found" text="Try a different search." /> : (
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b border-taupe/20 text-xs uppercase tracking-wider text-muted"><tr><th className="p-3">Name</th><th>Email</th><th>Phone</th><th>Joined</th><th>Orders</th><th>Verified spend</th></tr></thead>
            <tbody className="divide-y divide-taupe/15">{data.results.map((c) => (
              <tr key={c.id} className="cursor-pointer hover:bg-blush/30" onClick={() => setOpen(c.id)}>
                <td className="p-3"><button className="font-medium text-burgundy underline-offset-4 hover:underline" onClick={() => setOpen(c.id)}>{c.name}</button>{c.role === 'staff' && <span className="ml-2 rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-800">Staff</span>}</td>
                <td className="break-all">{c.email}</td><td>{c.phone || '—'}</td><td>{new Date(c.date_joined).toLocaleDateString('en-NG')}</td><td>{c.order_count}</td><td>{naira(c.verified_spend)}</td></tr>))}</tbody>
          </table>)}
        <Pager page={page} count={data?.count ?? 0} onPage={setPage} />
      </div>
      {data && <p className="mt-2 text-xs text-muted">{data.count} {data.count === 1 ? 'account' : 'accounts'}</p>}
      {open !== null && <Detail id={open} onClose={() => setOpen(null)} />}
    </div>
  )
}
