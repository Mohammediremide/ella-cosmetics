import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { api, ApiError, fieldError } from '../../lib/api'
import { useToast } from '../../lib/toast'
import { Field, Skeleton } from '../../components/ui'

const text: [string, string][] = [['store_name', 'Store name'], ['announcement', 'Announcement bar text'], ['contact_email', 'Contact email'], ['contact_phone', 'Contact phone'],
  ['instagram_url', 'Instagram URL'], ['whatsapp_number', 'WhatsApp number (international, e.g. 2348012345678)'], ['bank_name', 'Bank name'], ['account_name', 'Account name'], ['account_number', 'Account number (10 digits)'],
  ['currency_symbol', 'Currency symbol'], ['delivery_fee', 'Delivery fee (₦)'], ['pickup_instructions', 'Pickup instructions'], ['default_low_stock_threshold', 'Default low-stock threshold'], ['new_arrival_days', 'Days a product counts as NEW'],
  ['unpaid_order_hours', 'Cancel unpaid orders after (hours)'], ['legal_business_name', 'Registered business name (for legal pages)'], ['business_address', 'Business address (for legal pages)']]
const areas: [string, string, string][] = [['delivery_terms', 'Delivery terms (shown on the Terms page)', 'Areas you deliver to, how long it usually takes, charges…'], ['returns_terms', 'Returns & refunds policy (shown on the Terms page)', 'Your own policy in plain words']]

export default function StoreSettings() {
  const qc = useQueryClient(), toast = useToast()
  const [err, setErr] = useState<unknown>(null)
  const { data } = useQuery({ queryKey: ['admin', 'settings'], queryFn: () => api<any>('/admin/settings/') })
  const { register, handleSubmit, formState: { isSubmitting, isDirty } } = useForm<any>({ values: data, resetOptions: { keepDirtyValues: true } })  // a background refetch must never wipe what the admin is typing
  if (!data) return <Skeleton className="h-96" />
  const save = handleSubmit(async (d) => {
    setErr(null)
    try { await api('/admin/settings/', { method: 'PATCH', body: d }); qc.invalidateQueries({ queryKey: ['settings'] }); qc.invalidateQueries({ queryKey: ['admin', 'settings'] }); toast('Settings saved') }
    catch (e) { setErr(e); toast(e instanceof ApiError ? 'Please fix the highlighted fields' : 'Save failed', 'error') }
  })
  return (
    <form onSubmit={save} className="max-w-2xl space-y-4">
      <h1 className="text-4xl">Store settings</h1>
      <p className="text-sm text-muted">Bank details are shown only to customers who place an order. The WhatsApp number below is used for every WhatsApp link on the site.</p>
      <div className="grid gap-4 sm:grid-cols-2">{text.map(([k, l]) => <Field key={k} label={l} htmlFor={k} error={fieldError(err, k)}><input id={k} className="input" {...register(k)} /></Field>)}</div>
      {areas.map(([k, l, ph]) => <Field key={k} label={l} htmlFor={k} error={fieldError(err, k)}><textarea id={k} rows={4} className="input py-3" placeholder={ph} {...register(k)} /></Field>)}
      <div className="flex flex-wrap gap-6 text-sm">{[['delivery_enabled', 'Offer delivery'], ['pickup_enabled', 'Offer pickup']].map(([k, l]) => <label key={k} className="flex min-h-[44px] items-center gap-2"><input type="checkbox" className="h-4 w-4 accent-burgundy" {...register(k)} /> {l}</label>)}</div>
      <button className="btn-primary" disabled={isSubmitting || !isDirty}>{isSubmitting ? 'Saving…' : 'Save settings'}</button>
    </form>
  )
}
