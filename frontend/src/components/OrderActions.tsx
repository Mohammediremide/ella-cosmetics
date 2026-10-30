import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, ApiError, fieldError, naira } from '../lib/api'
import { useToast } from '../lib/toast'
import type { Order } from '../lib/types'
import { Modal } from './ui'

export type Action = { kind: 'payment' | 'fulfilment'; status: string; label: string; warn?: string; needsReason?: boolean; danger?: boolean }

/** Which admin actions make sense for an order right now (the backend re-validates every one of them). */
export function actionsFor(o: Order): Action[] {
  const a: Action[] = []
  if (o.fulfilment_status === 'cancelled') return a
  if (o.payment_status !== 'verified')
    a.push({ kind: 'payment', status: 'verified', label: 'Verify payment', warn: `Only confirm after you have seen exactly ${naira(o.total)} for ${o.reference} in the bank account. The customer will see “Payment Successful”.` })
  if (o.payment_status !== 'rejected' && o.payment_status !== 'verified')
    a.push({ kind: 'payment', status: 'rejected', label: 'Reject payment', needsReason: true, danger: true, warn: 'The customer will see your reason and be asked to contact you on WhatsApp.' })
  if (o.payment_status === 'verified' && o.fulfilment_status === 'pending')
    a.push({ kind: 'payment', status: 'pending_verification', label: 'Undo verification', warn: 'Moves the payment back to “Awaiting Verification”.', danger: true })
  const next = ({ pending: 'processing', processing: 'dispatched', dispatched: 'delivered' } as Record<string, string>)[o.fulfilment_status]
  if (next && o.payment_status === 'verified') a.push({ kind: 'fulfilment', status: next, label: `Mark ${next}` })
  if (['pending', 'processing'].includes(o.fulfilment_status)) a.push({ kind: 'fulfilment', status: 'cancelled', label: 'Cancel order', danger: true, warn: 'The reserved items return to stock. This cannot be undone.' })
  return a
}

/** Confirmation dialog + mutation for any admin order action (reject requires a reason). */
export function ConfirmAction({ order, action, onClose, onDone }: { order: Order | null; action: Action | null; onClose: () => void; onDone: (o: Order) => void }) {
  const qc = useQueryClient(), toast = useToast()
  const [reason, setReason] = useState('')
  const [err, setErr] = useState<unknown>(null)
  const run = useMutation({
    mutationFn: () => api<Order>(`/admin/orders/${order!.id}/${action!.kind}/`, { method: 'POST', body: { status: action!.status, ...(action!.needsReason ? { reason } : {}) } }),
    onSuccess: (o) => {
      qc.invalidateQueries({ queryKey: ['admin'] }); qc.invalidateQueries({ queryKey: ['products'] })
      toast(action!.status === 'verified' ? `Payment verified for ${o.reference}` : action!.status === 'rejected' ? `Payment rejected for ${o.reference}` : 'Order updated')
      setReason(''); setErr(null); onDone(o)
    },
    onError: (e) => { setErr(e); toast(e instanceof ApiError ? e.message : 'Update failed', 'error') },
  })
  const close = () => { setReason(''); setErr(null); onClose() }
  const reasonErr = fieldError(err, 'reason')
  return (
    <Modal open={!!action && !!order} title={action?.label ?? ''} onClose={close}>
      <p className="text-sm">{action?.warn ?? 'Update this order?'}</p>
      {action?.needsReason && (
        <div className="mt-4">
          <label className="label" htmlFor="why">Reason (required)</label>
          <textarea id="why" rows={3} maxLength={500} className="input py-3" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. We received ₦20,000, not ₦25,000" />
          {reasonErr && <p className="field-error" role="alert">{reasonErr}</p>}
        </div>
      )}
      <div className="mt-5 flex justify-end gap-3">
        <button className="btn-ghost" onClick={close}>Go back</button>
        <button className="btn-primary" disabled={run.isPending || (!!action?.needsReason && !reason.trim())} onClick={() => run.mutate()}>{run.isPending ? 'Saving…' : 'Confirm'}</button>
      </div>
    </Modal>
  )
}
