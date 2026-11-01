import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Clock, Copy, MessageCircle, XCircle } from 'lucide-react'
import { api, ApiError, naira, when } from '../lib/api'
import { useToast } from '../lib/toast'
import type { Order } from '../lib/types'
import { Empty, ErrorState, Skeleton, StatusBadge } from '../components/ui'

const STEPS = [
  'Transfer the exact order total to the bank account shown.',
  'Open WhatsApp using the “Send Receipt on WhatsApp” button.',
  'Attach and send your actual bank transfer receipt to Ella Cosmetics.',
  'Come back here and press “Done — I’ve Sent the Receipt”.',
  'Wait while we verify the payment. We’ll update this page.',
]

export default function OrderPage() {
  const { reference } = useParams()
  const [sp] = useSearchParams()
  const toast = useToast()
  const qc = useQueryClient()
  const [copied, setCopied] = useState(false)
  const key = ['orders', reference]
  const { data: o, isLoading, error, refetch } = useQuery({
    queryKey: key, retry: false, queryFn: () => api<Order>(`/orders/${reference}/`),
    refetchInterval: (q) => (q.state.data?.payment_status === 'pending_verification' ? 30_000 : false), // pick up the admin's decision
  })
  const done = useMutation({
    mutationFn: () => api<Order>(`/orders/${reference}/submit-payment/`, { method: 'POST' }),
    onSuccess: (d) => { qc.setQueryData(key, d); qc.invalidateQueries({ queryKey: ['orders', 'list'] }); toast('Thanks! We’ll check your payment shortly.') },
    onError: (e) => toast(e instanceof ApiError ? e.message : 'Could not send. Please try again.', 'error'),
  })
  if (isLoading) return <div className="container-x py-10"><Skeleton className="h-96" /></div>
  if (error instanceof ApiError && error.status === 404) return <Empty title="Order not found" action={<Link className="btn-primary" to="/account">My orders</Link>} />
  if (error || !o) return <ErrorState onRetry={() => refetch()} />

  const copy = async () => { try { await navigator.clipboard.writeText(o.bank!.account_number); setCopied(true); toast('Account number copied'); setTimeout(() => setCopied(false), 2000) } catch { toast('Copy failed — please select the number manually', 'error') } }
  const cancelled = o.fulfilment_status === 'cancelled'
  const needsPayment = !cancelled && ['awaiting_payment', 'rejected'].includes(o.payment_status)
  const waiting = !cancelled && o.payment_status === 'pending_verification'
  const paid = o.payment_status === 'verified'
  const bankReady = !!o.bank?.account_number
  const WaBtn = ({ label = 'Send Receipt on WhatsApp', outline = false }: { label?: string; outline?: boolean }) => o.whatsapp_url
    ? <a className={outline ? 'btn-outline w-full sm:w-auto' : 'btn-primary w-full sm:w-auto'} href={o.whatsapp_url} target="_blank" rel="noreferrer"><MessageCircle size={18} aria-hidden /> {label}</a>
    : <p className="text-sm text-muted">WhatsApp isn’t set up yet. Please keep your order number <strong>{o.reference}</strong> and contact the store directly.</p>

  return (
    <div className="container-x max-w-3xl py-10">
      {sp.get('placed') && (
        <div className="mb-8 flex items-start gap-3 rounded-brand bg-blush/60 p-5"><CheckCircle2 className="mt-0.5 shrink-0 text-burgundy" aria-hidden />
          <div><h1 className="text-3xl">Thank you, your order is saved</h1><p className="mt-1 text-sm">Order number <strong className="tracking-wider">{o.reference}</strong>. Complete the bank transfer below to confirm it.</p></div></div>
      )}
      {!sp.get('placed') && <h1 className="text-4xl">Order {o.reference}</h1>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted">Payment</span><StatusBadge value={o.payment_tone} label={o.payment_status_display} />
        <span className="ml-2 text-xs text-muted">Order</span><StatusBadge value={o.fulfilment_status} label={o.fulfilment_status_display} />
      </div>

      {paid && (
        <section className="mt-8 rounded-brand border border-emerald-200 bg-emerald-50 p-6" aria-live="polite">
          <h2 className="flex items-center gap-2 text-2xl text-emerald-900"><CheckCircle2 aria-hidden /> Payment Successful</h2>
          <p className="mt-2 text-sm text-emerald-900">We confirmed your transfer{o.payment_reviewed_at ? ` on ${when(o.payment_reviewed_at)}` : ''}. Your order status is now <strong>{o.fulfilment_status_display}</strong>. Payment received doesn’t mean delivered, so follow the order status above.</p>
        </section>
      )}

      {waiting && (
        <section className="mt-8 rounded-brand border border-amber-200 bg-amber-50 p-6" aria-live="polite">
          <h2 className="flex items-center gap-2 text-2xl text-amber-900"><Clock aria-hidden /> Processing — Awaiting Verification</h2>
          <p className="mt-2 text-sm text-amber-900">You told us you sent your receipt{o.payment_submitted_at ? ` on ${when(o.payment_submitted_at)}` : ''}. An admin will now check that the money arrived in our bank account. This is <strong>not</strong> a confirmation of payment yet.</p>
          <div className="mt-4"><WaBtn label="Reopen WhatsApp to send or resend receipt" outline /></div>
        </section>
      )}

      {o.payment_status === 'rejected' && !cancelled && (
        <section className="mt-8 rounded-brand border border-red-200 bg-red-50 p-6" role="alert">
          <h2 className="flex items-center gap-2 text-2xl text-red-900"><XCircle aria-hidden /> Payment Rejected</h2>
          <p className="mt-2 text-sm text-red-900">We couldn’t verify your payment.</p>
          {o.payment_rejection_reason && <p className="mt-2 rounded-brand bg-surface/70 p-3 text-sm"><span className="font-medium">Reason from Ella Cosmetics:</span> {o.payment_rejection_reason}</p>}
          <p className="mt-3 text-sm text-red-900">Please contact us on WhatsApp so we can help. If you have now paid the correct amount, send the receipt and press “Done” again below.</p>
          {o.whatsapp_support_url && <a className="btn-primary mt-4 w-full sm:w-auto" href={o.whatsapp_support_url} target="_blank" rel="noreferrer"><MessageCircle size={18} aria-hidden /> Contact Ella Cosmetics on WhatsApp</a>}
        </section>
      )}

      {cancelled && <p role="status" className="mt-8 rounded-brand bg-stone-100 p-4 text-sm">This order was cancelled. If you think this is a mistake, please contact the store.</p>}

      {needsPayment && (
        <section className="card mt-8 p-6" aria-labelledby="pay">
          <h2 id="pay" className="text-2xl">Pay by bank transfer</h2>
          <p className="mt-1 text-sm text-muted">Transfer exactly <strong className="text-ink">{naira(o.total)}</strong>. Payment is by manual bank transfer and is confirmed only after we verify it.</p>
          {bankReady ? (
            <dl className="mt-4 grid gap-3 rounded-brand bg-blush/30 p-4 text-sm sm:grid-cols-3">
              <div><dt className="text-muted">Bank name</dt><dd className="font-medium">{o.bank!.bank_name}</dd></div>
              <div><dt className="text-muted">Account name</dt><dd className="font-medium">{o.bank!.account_name}</dd></div>
              <div><dt className="text-muted">Account number</dt><dd className="flex items-center gap-1 text-lg font-semibold tracking-wider">{o.bank!.account_number}
                <button type="button" onClick={copy} className="btn-ghost min-h-10 px-2" aria-label="Copy account number"><Copy size={16} />{copied && <span className="text-xs font-normal">Copied</span>}</button></dd></div>
            </dl>
          ) : <p className="mt-4 rounded-brand bg-amber-50 p-3 text-sm text-amber-900">Bank details aren’t available yet. Please contact the store on WhatsApp to get them.</p>}

          <h3 className="mt-6 font-sans text-base font-semibold">What to do next</h3>
          <ol className="mt-2 space-y-2 text-sm">
            {STEPS.map((t, i) => <li key={i} className="flex gap-3"><span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-burgundy text-xs font-semibold text-white">{i + 1}</span><span>{t}</span></li>)}
          </ol>
          <div className="mt-6 flex flex-col gap-3 border-t border-taupe/20 pt-5 sm:flex-row">
            <WaBtn />
            <button className="btn-outline w-full sm:w-auto" disabled={done.isPending} onClick={() => done.mutate()}>{done.isPending ? 'Sending…' : 'Done — I’ve Sent the Receipt'}</button>
          </div>
          <p className="mt-3 text-xs text-muted">WhatsApp opens with your order details filled in. You must press send yourself and attach the receipt manually. Pressing “Done” does not confirm payment: it only tells us to look for it.</p>
        </section>
      )}

      <section className="card mt-8 p-6">
        <h2 className="text-2xl">Items</h2>
        <ul className="mt-4 divide-y divide-taupe/15 text-sm">{o.items.map((i) => <li key={i.id} className="flex justify-between gap-3 py-3"><span>{i.product_name} × {i.quantity}<span className="block text-xs text-muted">{naira(i.unit_price)} each</span></span><span>{naira(i.line_total)}</span></li>)}</ul>
        <dl className="mt-3 space-y-1 border-t border-taupe/20 pt-3 text-sm">
          <div className="flex justify-between"><dt>Subtotal</dt><dd>{naira(o.subtotal)}</dd></div>
          {Number(o.delivery_fee) > 0 && <div className="flex justify-between"><dt>Delivery</dt><dd>{naira(o.delivery_fee)}</dd></div>}
          <div className="flex justify-between text-lg font-medium"><dt>Total</dt><dd>{naira(o.total)}</dd></div>
        </dl>
        <p className="mt-4 text-sm text-muted">{o.delivery_method === 'delivery' ? `Delivery to: ${o.delivery_address}` : 'Pickup'} · {o.customer_name}, {o.customer_phone}</p>
      </section>
      <Link to="/account" className="mt-6 inline-block text-sm text-burgundy underline-offset-4 hover:underline">← All my orders</Link>
    </div>
  )
}
