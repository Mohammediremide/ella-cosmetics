import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, naira, when } from '../../lib/api'
import type { Order, Page } from '../../lib/types'
import { Action, actionsFor, ConfirmAction } from '../../components/OrderActions'
import { Empty, Pager, Skeleton, StatusBadge } from '../../components/ui'

export default function Orders() {
  const [sp] = useSearchParams()
  const [search, setSearch] = useState(sp.get('search') ?? ''), [pay, setPay] = useState(''), [ful, setFul] = useState(''), [page, setPage] = useState(1)
  const [sel, setSel] = useState<Order | null>(null)
  const [pending, setPending] = useState<Action | null>(null)
  const qs = new URLSearchParams({ search, page: String(page), ...(pay && { payment_status: pay }), ...(ful && { fulfilment_status: ful }) })
  const { data, isLoading } = useQuery({ queryKey: ['admin', 'orders', qs.toString()], queryFn: () => api<Page<Order>>(`/admin/orders/?${qs}`) })
  const actions = actionsFor

  return (
    <div>
      <h1 className="text-4xl">Orders</h1>
      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <input className="input" type="search" placeholder="Search reference, name, phone, email" aria-label="Search orders" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }} />
        <select className="input" aria-label="Payment status" value={pay} onChange={(e) => { setPay(e.target.value); setPage(1) }}><option value="">All payments</option><option value="awaiting_payment">Awaiting Payment</option><option value="pending_verification">Awaiting Verification</option><option value="verified">Payment Successful</option><option value="rejected">Payment Rejected</option></select>
        <select className="input" aria-label="Order status" value={ful} onChange={(e) => { setFul(e.target.value); setPage(1) }}><option value="">All order statuses</option>{['pending', 'processing', 'dispatched', 'delivered', 'cancelled'].map((s) => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}</select>
      </div>
      <div className="card mt-4 overflow-x-auto">
        {isLoading ? <Skeleton className="h-48" /> : !data?.results.length ? <Empty title="No orders found" /> : (
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-taupe/20 text-xs uppercase tracking-wider text-muted"><tr><th className="p-3">Reference</th><th>Customer</th><th>Date</th><th>Items</th><th>Total</th><th>Payment</th><th>Order</th></tr></thead>
            <tbody className="divide-y divide-taupe/15">{data.results.map((o) => (
              <tr key={o.reference} className="cursor-pointer hover:bg-blush/30" onClick={() => setSel(o)}>
                <td className="p-3"><button className="font-medium text-burgundy underline-offset-4 hover:underline" onClick={() => setSel(o)}>{o.reference}</button></td><td>{o.customer_name}</td>
                <td>{new Date(o.created_at).toLocaleDateString('en-NG')}</td><td>{o.item_count}</td><td>{naira(o.total)}</td>
                <td><StatusBadge value={o.payment_tone} label={o.payment_status_display} /></td><td><StatusBadge value={o.fulfilment_status} label={o.fulfilment_status_display} /></td></tr>))}</tbody>
          </table>)}
        <Pager page={page} count={data?.count ?? 0} onPage={setPage} />
      </div>

      {sel && (
        <div className="fixed inset-0 z-40 flex justify-end bg-charcoal/40" onMouseDown={(e) => e.target === e.currentTarget && setSel(null)}>
          <aside role="dialog" aria-modal="true" aria-label={`Order ${sel.reference}`} className="h-full w-full max-w-lg overflow-y-auto bg-ivory p-6">
            <div className="flex items-start justify-between"><h2 className="text-3xl">{sel.reference}</h2><button className="btn-ghost" onClick={() => setSel(null)}>Close</button></div>
            <div className="mt-2 flex gap-2"><StatusBadge value={sel.payment_tone} label={sel.payment_status_display} /><StatusBadge value={sel.fulfilment_status} label={sel.fulfilment_status_display} /></div>
            <section className="mt-5 text-sm"><p className="font-medium">{sel.customer_name} · {sel.customer_phone}</p><p className="text-muted">{sel.customer_email}</p>
              <p className="mt-2">{sel.delivery_method === 'delivery' ? `Delivery: ${sel.delivery_address}` : 'Pickup'}</p>{sel.note && <p className="mt-1 text-muted">Note: {sel.note}</p>}</section>
            <section className="mt-3 rounded-brand bg-blush/30 p-3 text-xs">
              <p>Receipt submitted: <strong>{when(sel.payment_submitted_at)}</strong></p>
              {sel.payment_reviewed_at && <p>Reviewed: {when(sel.payment_reviewed_at)} by {sel.payment_reviewed_by}</p>}
              {sel.payment_rejection_reason && <p>Rejection reason: {sel.payment_rejection_reason}</p>}
              {sel.customer_whatsapp_url && <a className="mt-1 inline-block font-medium text-burgundy underline" href={sel.customer_whatsapp_url} target="_blank" rel="noreferrer">Chat with customer on WhatsApp</a>}
            </section>
            <section className="card mt-5 p-4 text-sm"><p className="mb-2 text-xs uppercase tracking-wider text-muted">Items at time of purchase</p>
              {sel.items.map((i) => <div key={i.id} className="flex justify-between py-1"><span>{i.product_name} × {i.quantity} <span className="text-muted">@ {naira(i.unit_price)}</span></span><span>{naira(i.line_total)}</span></div>)}
              <div className="mt-2 flex justify-between border-t border-taupe/20 pt-2"><span>Delivery</span><span>{naira(sel.delivery_fee)}</span></div>
              <div className="flex justify-between text-base font-medium"><span>Total</span><span>{naira(sel.total)}</span></div></section>
            <div className="mt-5 flex flex-wrap gap-2">{actions(sel).map((a) => <button key={a.kind + a.status} className={a.danger ? 'btn-outline' : 'btn-primary'} onClick={() => setPending(a)}>{a.label}</button>)}</div>
            {!!sel.audit?.length && <section className="mt-6"><p className="mb-2 text-xs uppercase tracking-wider text-muted">History</p>
              <ul className="space-y-1 text-xs text-ink/80">{sel.audit.map((h, i) => <li key={i}>{new Date(h.at).toLocaleString('en-NG')} — {h.field}: {h.from} → <strong>{h.to}</strong> by {h.by}</li>)}</ul></section>}
          </aside>
        </div>
      )}
      <ConfirmAction order={sel} action={pending} onClose={() => setPending(null)} onDone={(o) => { setSel(o); setPending(null) }} />
    </div>
  )
}
