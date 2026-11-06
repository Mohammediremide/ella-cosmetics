import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { api, ApiError, naira, when } from '../../lib/api'
import { useToast } from '../../lib/toast'
import type { Order, Page } from '../../lib/types'
import { Action, actionsFor, ConfirmAction } from '../../components/OrderActions'
import { Empty, Modal, Pager, Skeleton, StatusBadge } from '../../components/ui'

export default function Orders() {
  const qc = useQueryClient(), toast = useToast()
  const [sp] = useSearchParams()
  const [tab, setTab] = useState<'without' | 'with'>('without')
  const [search, setSearch] = useState(sp.get('search') ?? ''), [pay, setPay] = useState(''), [ful, setFul] = useState(''), [page, setPage] = useState(1)
  const [sel, setSel] = useState<Order | null>(null)
  const [pending, setPending] = useState<Action | null>(null)
  const [del, setDel] = useState<Order | null>(null)
  const [dispatchDraft, setDispatchDraft] = useState('')
  const qs = new URLSearchParams({ search, page: String(page), dispatch_requested: String(tab === 'with'), ...(pay && { payment_status: pay }), ...(ful && { fulfilment_status: ful }) })
  const { data, isLoading } = useQuery({ queryKey: ['admin', 'orders', qs.toString()], queryFn: () => api<Page<Order>>(`/admin/orders/?${qs}`) })
  const overview = useQuery({ queryKey: ['admin', 'overview'], queryFn: () => api<{ orders_with_dispatch: number; orders_without_dispatch: number }>('/admin/overview/') })
  const actions = actionsFor
  const updateDispatch = useMutation({
    mutationFn: (status: string) => api<Order>(`/admin/orders/${sel!.id}/dispatch/`, { method: 'POST', body: { status } }),
    onSuccess: (o) => {
      qc.invalidateQueries({ queryKey: ['admin'] })
      setSel(o); setDispatchDraft(o.dispatch_status)
      toast(`Dispatch status updated for ${o.reference}`)
    },
    onError: (e) => toast(e instanceof ApiError ? e.message : 'Dispatch status could not be updated', 'error'),
  })
  const remove = useMutation({
    mutationFn: (o: Order) => api(`/admin/orders/${o.id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin'] }); qc.invalidateQueries({ queryKey: ['products'] }); qc.invalidateQueries({ queryKey: ['orders'] })
      toast(`Order ${del?.reference} deleted`); setDel(null); setSel(null)
    },
    onError: (e) => toast(e instanceof ApiError ? e.message : 'Order could not be deleted', 'error'),
  })

  return (
    <div>
      <h1 className="text-4xl">Orders</h1>
      <div role="tablist" aria-label="Order dispatch category" className="mt-5 flex flex-wrap gap-2">
        <button role="tab" aria-selected={tab === 'without'} onClick={() => { setTab('without'); setPage(1) }}
          className={`min-h-[44px] rounded-full border px-4 text-sm ${tab === 'without' ? 'border-burgundy bg-burgundy text-white' : 'border-taupe/50 bg-surface hover:border-burgundy'}`}>
          Orders Without Dispatch <span className="ml-1 font-semibold">({overview.data?.orders_without_dispatch ?? '…'})</span>
        </button>
        <button role="tab" aria-selected={tab === 'with'} onClick={() => { setTab('with'); setPage(1) }}
          className={`min-h-[44px] rounded-full border px-4 text-sm ${tab === 'with' ? 'border-burgundy bg-burgundy text-white' : 'border-taupe/50 bg-surface hover:border-burgundy'}`}>
          Orders With Dispatch <span className="ml-1 font-semibold">({overview.data?.orders_with_dispatch ?? '…'})</span>
        </button>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <input className="input" type="search" placeholder="Search reference, name, phone, email" aria-label="Search orders" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }} />
        <select className="input" aria-label="Payment status" value={pay} onChange={(e) => { setPay(e.target.value); setPage(1) }}><option value="">All payments</option><option value="awaiting_payment">Awaiting Payment</option><option value="pending_verification">Awaiting Verification</option><option value="verified">Payment Successful</option><option value="rejected">Payment Rejected</option></select>
        <select className="input" aria-label="Order status" value={ful} onChange={(e) => { setFul(e.target.value); setPage(1) }}><option value="">All order statuses</option>{['pending', 'processing', 'dispatched', 'delivered', 'cancelled'].map((s) => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}</select>
      </div>
      <div className="card mt-4 overflow-x-auto">
        {isLoading ? <Skeleton className="h-48" /> : !data?.results.length ? <Empty title="No orders found" /> : (
          <table className={`w-full text-left text-sm ${tab === 'with' ? 'min-w-[1100px]' : 'min-w-[720px]'}`}>
            <thead className="border-b border-taupe/20 text-xs uppercase tracking-wider text-muted"><tr><th className="p-3">Reference</th><th>Customer</th>{tab === 'with' && <><th>Delivery address</th><th>Dispatch phone</th><th>Instructions</th><th>Dispatch</th></>}<th>Date</th><th>Items</th><th>Total</th><th>Payment</th><th>Order</th></tr></thead>
            <tbody className="divide-y divide-taupe/15">{data.results.map((o) => (
              <tr key={o.reference} className="cursor-pointer hover:bg-blush/30" onClick={() => { setSel(o); setDispatchDraft(o.dispatch_status) }}>
                <td className="p-3"><button className="font-medium text-burgundy underline-offset-4 hover:underline" onClick={() => { setSel(o); setDispatchDraft(o.dispatch_status) }}>{o.reference}</button></td><td>{o.customer_name}</td>
                {tab === 'with' && <><td className="max-w-64 whitespace-normal py-2">{o.dispatch_address}, {o.dispatch_city}, {o.dispatch_state}</td><td>{o.dispatch_phone}</td><td className="max-w-48 whitespace-normal">{o.dispatch_instructions || '—'}</td><td><StatusBadge value={o.dispatch_status} label={o.dispatch_status_display} /></td></>}
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
            {sel.dispatch_requested && <section className="mt-4 rounded-brand border border-taupe/20 p-4">
              <h3 className="text-lg">Dispatch delivery</h3>
              <dl className="mt-2 space-y-1 text-sm">
                <div><dt className="inline text-muted">Address: </dt><dd className="inline">{sel.dispatch_address}</dd></div>
                <div><dt className="inline text-muted">State: </dt><dd className="inline">{sel.dispatch_state}</dd></div>
                <div><dt className="inline text-muted">City/area: </dt><dd className="inline">{sel.dispatch_city}</dd></div>
                <div><dt className="inline text-muted">Phone: </dt><dd className="inline">{sel.dispatch_phone}</dd></div>
                <div><dt className="inline text-muted">Instructions: </dt><dd className="inline">{sel.dispatch_instructions || 'None'}</dd></div>
              </dl>
              <div className="mt-4 flex flex-wrap items-end gap-2">
                <label className="flex-1 text-sm">Dispatch status
                  <select className="input mt-1" value={dispatchDraft} onChange={(e) => setDispatchDraft(e.target.value)}>
                    <option value="awaiting_dispatch">Awaiting Dispatch</option><option value="dispatched">Dispatched</option><option value="delivered">Delivered</option>
                  </select>
                </label>
                <button className="btn-primary" disabled={updateDispatch.isPending || dispatchDraft === sel.dispatch_status} onClick={() => updateDispatch.mutate(dispatchDraft)}>
                  {updateDispatch.isPending ? 'Saving…' : 'Save dispatch status'}
                </button>
              </div>
            </section>}
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
            {sel.payment_status !== 'verified' && !['dispatched', 'delivered'].includes(sel.fulfilment_status) && (
              <button className="btn-outline mt-5 border-red-300 text-red-700" onClick={() => setDel(sel)}><Trash2 size={16} aria-hidden /> Delete order</button>
            )}
            {!!sel.audit?.length && <section className="mt-6"><p className="mb-2 text-xs uppercase tracking-wider text-muted">History</p>
              <ul className="space-y-1 text-xs text-ink/80">{sel.audit.map((h, i) => <li key={i}>{new Date(h.at).toLocaleString('en-NG')} — {h.field}: {h.from} → <strong>{h.to}</strong> by {h.by}</li>)}</ul></section>}
          </aside>
        </div>
      )}
      <ConfirmAction order={sel} action={pending} onClose={() => setPending(null)} onDone={(o) => { setSel(o); setPending(null) }} />
      <Modal open={!!del} title="Delete order permanently?" onClose={() => !remove.isPending && setDel(null)}>
        <p className="text-sm">This permanently deletes order {del?.reference} and its history. Any reserved items will be returned to stock. Paid, dispatched, or delivered orders cannot be deleted.</p>
        <div className="mt-5 flex justify-end gap-3">
          <button className="btn-ghost" disabled={remove.isPending} onClick={() => setDel(null)}>Cancel</button>
          <button className="btn-primary bg-red-700" disabled={remove.isPending} onClick={() => del && remove.mutate(del)}>{remove.isPending ? 'Deleting…' : 'Delete order'}</button>
        </div>
      </Modal>
    </div>
  )
}
