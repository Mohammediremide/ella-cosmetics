import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Eye, Users } from 'lucide-react'
import { api, naira } from '../../lib/api'
import { ErrorState, Skeleton, StatusBadge } from '../../components/ui'
import type { Order } from '../../lib/types'

interface Analytics {
  today: Tot; last_7_days: Tot; last_30_days: Tot; all_time: Tot; days: number
  daily: { day: string; page_views: number; visitors: number }[]; top_pages: { path: string; page_views: number }[]
}
type Tot = { page_views: number; visitors: number }

function Visits() {
  const [days, setDays] = useState(14)
  const { data: a, isLoading, isError } = useQuery({ queryKey: ['admin', 'analytics', days], queryFn: () => api<Analytics>(`/admin/analytics/?days=${days}`) })
  if (isError) return <ErrorState message="Couldn’t load visit statistics." />
  const max = Math.max(1, ...(a?.daily.map((d) => d.visitors) ?? [1]))
  const cards: [string, Tot | undefined][] = [['Today', a?.today], ['Last 7 days', a?.last_7_days], ['Last 30 days', a?.last_30_days], ['All time', a?.all_time]]
  return (
    <section className="mt-10" aria-labelledby="visits-h">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h2 id="visits-h" className="text-2xl">Website visits</h2><p className="text-xs text-muted">Visitors are counted once per day. No cookies or IP addresses are stored; your own visits, bots and admin pages are excluded.</p></div>
        <select className="input w-auto" aria-label="Chart period" value={days} onChange={(e) => setDays(Number(e.target.value))}>{[7, 14, 30, 90].map((d) => <option key={d} value={d}>Last {d} days</option>)}</select>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {cards.map(([label, t]) => (
          <div key={label} className="card p-4">
            <p className="text-xs text-muted">{label}</p>
            {isLoading ? <Skeleton className="mt-2 h-9" /> : <>
              <p className="mt-1 flex items-center gap-2 font-serif text-3xl"><Users size={18} className="text-burgundy" aria-hidden />{t?.visitors.toLocaleString()}<span className="font-sans text-xs text-muted">visitors</span></p>
              <p className="mt-1 flex items-center gap-2 text-sm text-muted"><Eye size={14} aria-hidden />{t?.page_views.toLocaleString()} page views</p></>}
          </div>))}
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <div className="card p-4 lg:col-span-2">
          <p className="text-sm font-medium">Daily visitors</p>
          {isLoading ? <Skeleton className="mt-3 h-40" /> : (
            <div className="mt-3 flex h-40 items-end gap-[3px]" role="img" aria-label={`Bar chart of daily visitors over the last ${days} days. Total ${a?.daily.reduce((n, d) => n + d.visitors, 0)}.`}>
              {a?.daily.map((d) => (
                <div key={d.day} className="group relative flex h-full flex-1 items-end" title={`${d.day}: ${d.visitors} visitors, ${d.page_views} page views`}>
                  <div className="w-full rounded-t bg-burgundy/80 transition-colors group-hover:bg-burgundy" style={{ height: `${Math.max(d.visitors ? 4 : 1, (d.visitors / max) * 100)}%`, opacity: d.visitors ? 1 : 0.2 }} />
                </div>))}
            </div>)}
          <div className="mt-1 flex justify-between text-[11px] text-muted"><span>{a?.daily[0]?.day}</span><span>{a?.daily[a.daily.length - 1]?.day}</span></div>
        </div>
        <div className="card p-4">
          <p className="text-sm font-medium">Most viewed pages</p>
          <ul className="mt-3 space-y-2 text-sm">
            {a?.top_pages.map((p) => <li key={p.path} className="flex justify-between gap-3"><span className="truncate">{p.path}</span><span className="shrink-0 text-muted">{p.page_views}</span></li>)}
            {a && !a.top_pages.length && <li className="text-muted">No visits recorded yet.</li>}
          </ul>
        </div>
      </div>
    </section>
  )
}

export default function Overview() {
  const { data: d, isLoading, isError, refetch } = useQuery({ queryKey: ['admin', 'overview'], queryFn: () => api<any>('/admin/overview/') })
  if (isError) return <ErrorState onRetry={() => refetch()} />
  const cards: [string, string | number, string?][] | undefined = d && [
    ['Needs payment verification', d.awaiting_verification, '/admin/payments'], ['Awaiting payment', d.awaiting_payment, '/admin/payments'], ['Processing orders', d.processing, '/admin/orders'], ['Verified sales', naira(d.verified_sales_total)],
    ['Total products', d.total_products, '/admin/products'], ['In stock', d.in_stock], ['Low stock', d.low_stock], ['Out of stock', d.out_of_stock],
  ]
  return (
    <div>
      <h1 className="text-4xl">Overview</h1>
      <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {isLoading ? Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-24" />) : cards!.map(([k, v, to]) => {
          const inner = <><p className="text-xs text-muted">{k}</p><p className="mt-2 font-serif text-3xl">{v}</p></>
          return to ? <Link key={k} to={to} className="card block p-4 hover:border-burgundy">{inner}</Link> : <div key={k} className="card p-4">{inner}</div>
        })}
      </div>
      <p className="mt-2 text-xs text-muted">“Verified sales” counts only orders whose bank transfer you have confirmed. Pending orders are not revenue.</p>
      <Visits />
      <h2 className="mt-10 text-2xl">Recent orders</h2>
      <div className="card mt-3 divide-y divide-taupe/15">
        {d?.recent_orders.length === 0 && <p className="p-5 text-sm text-muted">No orders yet.</p>}
        {d?.recent_orders.map((o: Order) => (
          <Link key={o.reference} to={`/admin/orders?search=${o.reference}`} className="flex flex-wrap items-center justify-between gap-2 p-4 hover:bg-blush/30"><span className="font-medium">{o.reference}</span><span className="text-sm text-muted">{o.customer_name}</span>
            <span className="flex items-center gap-2"><StatusBadge value={o.payment_tone} label={o.payment_status_display} />{naira(o.total)}</span></Link>))}
      </div>
    </div>
  )
}
