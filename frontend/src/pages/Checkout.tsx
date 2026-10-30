import { useRef, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQueryClient } from '@tanstack/react-query'
import { api, ApiError, fieldError, naira } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useCart } from '../lib/cart'
import { useToast } from '../lib/toast'
import type { Order } from '../lib/types'
import { usePublicSettings } from '../components/Layout'
import { Field, Skeleton } from '../components/ui'

const schema = z.object({
  customer_name: z.string().trim().min(2, 'Enter your full name'),
  customer_phone: z.string().trim().regex(/^\+?[0-9\s-]{7,20}$/, 'Enter a valid phone number'),
  delivery_method: z.enum(['delivery', 'pickup']),
  delivery_address: z.string().trim().max(500).optional(),
  note: z.string().max(500).optional(),
}).refine((d) => d.delivery_method !== 'delivery' || !!d.delivery_address?.trim(), { path: ['delivery_address'], message: 'Enter your delivery address' })
type Form = z.infer<typeof schema>

export default function Checkout() {
  const { user, loading: authLoading } = useAuth()
  const { cart, loading, refresh } = useCart()
  const { data: s } = usePublicSettings()
  const nav = useNavigate(), toast = useToast(), qc = useQueryClient()
  const [serverErr, setServerErr] = useState<unknown>(null)
  const key = useRef(crypto.randomUUID()) // same key on retries => the server never creates a duplicate order
  const only = s && (s.delivery_enabled !== s.pickup_enabled) ? (s.delivery_enabled ? 'delivery' : 'pickup') : undefined
  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } = useForm<Form>({
    resolver: zodResolver(schema),
    values: { customer_name: user?.name ?? '', customer_phone: user?.phone ?? '', delivery_method: only ?? (s?.pickup_enabled ? 'pickup' : 'delivery'), delivery_address: '', note: '' },
  })
  const method = watch('delivery_method')

  if (authLoading || !s || loading) return <div className="container-x py-10"><Skeleton className="h-96" /></div>
  if (!user) return <Navigate to="/login?next=/checkout" replace />
  if (!cart.items.length) return <Navigate to="/cart" replace />
  const fee = method === 'delivery' ? Number(s.delivery_fee) : 0
  const none = !s.delivery_enabled && !s.pickup_enabled

  const submit = handleSubmit(async (d) => {
    setServerErr(null)
    try {
      const o = await api<Order>('/checkout/', { method: 'POST', body: { ...d, items: cart.items.map((l) => ({ product_id: l.product_id, quantity: l.quantity })) }, headers: { 'Idempotency-Key': key.current } } as any)
      qc.invalidateQueries({ queryKey: ['orders'] }); await refresh()
      nav(`/orders/${o.reference}?placed=1`, { replace: true })
    } catch (e) {
      setServerErr(e)
      toast(e instanceof ApiError ? e.message : 'Could not place order', 'error')
      if (e instanceof ApiError && e.code === 'validation_error') await refresh() // stock changed: show fresh cart
    }
  })

  return (
    <form onSubmit={submit} noValidate className="container-x grid gap-10 py-10 lg:grid-cols-5">
      <div className="space-y-5 lg:col-span-3">
        <h1 className="text-4xl">Checkout</h1>
        {none && <p role="alert" className="rounded-brand bg-blush p-4 text-sm">Ordering is temporarily unavailable. Please contact the store.</p>}
        <Field label="Full name" htmlFor="n" error={errors.customer_name?.message ?? fieldError(serverErr, 'customer_name')}><input id="n" className="input" autoComplete="name" {...register('customer_name')} /></Field>
        <Field label="Phone number" htmlFor="p" error={errors.customer_phone?.message ?? fieldError(serverErr, 'customer_phone')}><input id="p" className="input" inputMode="tel" autoComplete="tel" {...register('customer_phone')} /></Field>
        {s.delivery_enabled && s.pickup_enabled && (
          <fieldset><legend className="label">How would you like to receive your order?</legend>
            <div className="grid grid-cols-2 gap-3">
              {(['pickup', 'delivery'] as const).map((m) => (
                <label key={m} className={`card flex min-h-[44px] cursor-pointer items-center gap-2 p-3 text-sm ${method === m ? 'border-burgundy ring-1 ring-burgundy' : ''}`}>
                  <input type="radio" value={m} {...register('delivery_method')} className="accent-burgundy" /> {m === 'pickup' ? 'Pickup' : `Delivery (${naira(s.delivery_fee)})`}
                </label>))}
            </div></fieldset>
        )}
        {method === 'pickup' && s.pickup_instructions && <p className="text-sm text-muted">{s.pickup_instructions}</p>}
        {method === 'delivery' && <Field label="Delivery address" htmlFor="a" error={errors.delivery_address?.message ?? fieldError(serverErr, 'delivery_address')}><textarea id="a" rows={3} className="input py-3" autoComplete="street-address" {...register('delivery_address')} /></Field>}
        <Field label="Order note (optional)" htmlFor="o"><textarea id="o" rows={2} className="input py-3" {...register('note')} /></Field>
        {serverErr instanceof ApiError && fieldError(serverErr, 'problems') === undefined && !Object.keys(serverErr.fields).some((k) => ['customer_name', 'customer_phone', 'delivery_address'].includes(k)) && <p role="alert" className="field-error text-sm">{serverErr.message}</p>}
      </div>

      <aside className="card h-fit p-6 lg:col-span-2 lg:sticky lg:top-24">
        <h2 className="text-2xl">Your order</h2>
        <ul className="mt-4 space-y-3 text-sm">{cart.items.map((l) => <li key={l.product_id} className="flex justify-between gap-3"><span>{l.name} × {l.quantity}<span className="block text-xs text-muted">{naira(l.unit_price)} each</span></span><span>{naira(l.line_total)}</span></li>)}</ul>
        <dl className="mt-4 space-y-2 border-t border-taupe/20 pt-4 text-sm">
          <div className="flex justify-between"><dt>Subtotal</dt><dd>{naira(cart.subtotal)}</dd></div>
          {method === 'delivery' && <div className="flex justify-between"><dt>Delivery</dt><dd>{naira(fee)}</dd></div>}
          <div className="flex justify-between text-lg font-medium"><dt>Total to pay</dt><dd>{naira(Number(cart.subtotal) + fee)}</dd></div>
        </dl>
        <p className="mt-4 rounded-brand bg-blush/50 p-3 text-xs leading-relaxed">Payment is by <strong>manual bank transfer</strong>. After placing your order you’ll see the account details. Your order is confirmed once we verify the transfer.</p>
        <button className="btn-primary mt-5 w-full" disabled={isSubmitting || none}>{isSubmitting ? 'Placing order…' : 'Place order'}</button>
        <Link to="/cart" className="mt-3 block text-center text-sm text-muted hover:text-burgundy">Back to cart</Link>
      </aside>
    </form>
  )
}
