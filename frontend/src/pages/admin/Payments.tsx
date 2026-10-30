import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { MessageCircle } from 'lucide-react'
import { api, naira, when } from '../../lib/api'
import type { Order, Page } from '../../lib/types'
import { Action, ConfirmAction } from '../../components/OrderActions'
import { usePublicSettings } from '../../components/Layout'
import { Empty, Pager, Skeleton, StatusBadge } from '../../components/ui'

const TABS = [
  { key: 'pending_verification', label: 'Needs verification', ordering: 'payment_submitted_at', hint: 'Customers who pressed “Done”, oldest first. Check your bank account before verifying.' },
  { key: 'awaiting_payment', label: 'Awaiting payment', ordering: '-created_at', hint: 'Orders where the customer hasn’t said they’ve paid yet.' },
  { key: 'rejected', label: 'Rejected', ordering: '-payment_reviewed_at', hint: 'Payments you rejected. Customers can resubmit.' },
  { key: 'verified', label: 'Verified', ordering: '-payment_reviewed_at', hint: 'Payments confirmed as received.' },
]

export default function Payments() {
  const { data: s } = usePublicSettings()
  const [tab, setTab] = useState(TABS[0])
  const [page, setPage] = useState(1)
  const [target, setTarget] = useState<{ o: Order; a: Action } | null>(null)
  const { data, isLoading } = useQuery({ queryKey: ['admin', 'payments', tab.key, page], queryFn: () => api<Page<Order>>(`/admin/orders/?payment_status=${tab.key}&ordering=${tab.ordering}&page=${page}`) })
  const counts = useQuery({ queryKey: ['admin', 'overview'], queryFn: () => api<any>('/admin/overview/') })
  const badge = (k: string) => (k === 'pending_verification' ? counts.data?.awaiting_verification : k === 'awaiting_payment' ? counts.data?.awaiting_payment : undefined)

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-4xl">Payment Verification</h1><p className="mt-1 max-w-xl text-sm text-muted">Receipts arrive on the business WhatsApp. Only mark a payment as verified once the money has actually reached the bank account.</p></div>
        {s?.whatsapp_number && <a className="btn-outline" href={`https://wa.me/${s.whatsapp_number}`} target="_blank" rel="noreferrer"><MessageCircle size={16} aria-hidden /> Open business WhatsApp (+{s.whatsapp_number})</a>}
      </div>

      <div role="tablist" aria-label="Payment status" className="mt-6 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab.key === t.key} onClick={() => { setTab(t); setPage(1) }}
            className={`min-h-[44px] rounded-full border px-4 text-sm ${tab.key === t.key ? 'border-burgundy bg-burgundy text-white' : 'border-taupe/50 bg-white hover:border-burgundy'}`}>
            {t.label}{!!badge(t.key) && <span className={`ml-2 rounded-full px-2 py-0.5 text-xs font-semibold ${tab.key === t.key ? 'bg-white text-burgundy' : 'bg-burgundy text-white'}`}>{badge(t.key)}</span>}
          </button>))}
      </div>
      <p className="mt-3 text-sm text-muted">{tab.hint}</p>

      <div className="mt-4 space-y-3">
        {isLoading ? <Skeleton className="h-40" /> : !data?.results.length ? <div className="card"><Empty title="Nothing here" text={tab.key === 'pending_verification' ? 'No payments are waiting for verification.' : 'No orders in this list.'} /></div> : data.results.map((o) => {
          const acts = [] as Action[]
          if (o.payment_status !== 'verified' && o.fulfilment_status !== 'cancelled') acts.push({ kind: 'payment', status: 'verified', label: 'Verify payment', warn: `Only confirm after you have seen exactly ${naira(o.total)} for ${o.reference} in the bank account. The customer will see “Payment Successful”.` })
          if (['pending_verification', 'awaiting_payment'].includes(o.payment_status) && o.fulfilment_status !== 'cancelled') acts.push({ kind: 'payment', status: 'rejected', label: 'Reject payment', needsReason: true, danger: true, warn: 'The customer will see your reason and be asked to contact you on WhatsApp.' })
          return (
            <article key={o.reference} className="card p-4 sm:p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><h2 className="font-sans text-lg font-semibold tracking-wide">{o.reference}</h2><p className="text-sm text-muted">Ordered {when(o.created_at)}</p></div>
                <div className="text-right"><p className="text-xl font-semibold">{naira(o.total)}</p><StatusBadge value={o.payment_tone} label={o.payment_status_display} /></div>
              </div>
              <dl className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
                <div><dt className="inline text-muted">Customer: </dt><dd className="inline font-medium">{o.customer_name}</dd></div>
                <div><dt className="inline text-muted">Phone: </dt><dd className="inline">{o.customer_phone}</dd></div>
                <div><dt className="inline text-muted">Email: </dt><dd className="inline break-all">{o.customer_email}</dd></div>
                <div><dt className="inline text-muted">Receipt submitted: </dt><dd className="inline font-medium">{when(o.payment_submitted_at)}</dd></div>
                {o.payment_reviewed_at && <div><dt className="inline text-muted">Reviewed: </dt><dd className="inline">{when(o.payment_reviewed_at)} by {o.payment_reviewed_by}</dd></div>}
                {o.payment_rejection_reason && <div className="sm:col-span-2"><dt className="inline text-muted">Rejection reason: </dt><dd className="inline">{o.payment_rejection_reason}</dd></div>}
              </dl>
              <div className="mt-4 flex flex-wrap gap-2">
                {o.customer_whatsapp_url && <a className="btn-outline" href={o.customer_whatsapp_url} target="_blank" rel="noreferrer"><MessageCircle size={16} aria-hidden /> Chat with customer</a>}
                <Link className="btn-ghost" to={`/admin/orders?search=${o.reference}`}>View order</Link>
                <span className="flex-1" />
                {acts.map((a) => <button key={a.status} className={a.danger ? 'btn-outline' : 'btn-primary'} onClick={() => setTarget({ o, a })}>{a.label}</button>)}
              </div>
            </article>
          )
        })}
        <Pager page={page} count={data?.count ?? 0} onPage={setPage} />
      </div>
      <ConfirmAction order={target?.o ?? null} action={target?.a ?? null} onClose={() => setTarget(null)} onDone={() => setTarget(null)} />
    </div>
  )
}
