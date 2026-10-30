import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Minus, Plus, ShoppingBag } from 'lucide-react'
import { api, ApiError, naira } from '../lib/api'
import { useCart } from '../lib/cart'
import { useToast } from '../lib/toast'
import type { Product } from '../lib/types'
import { Empty, ErrorState, Img, Skeleton, StockBadge } from '../components/ui'

export default function ProductPage() {
  const { slug } = useParams()
  const { add, cart } = useCart()
  const toast = useToast()
  const [qty, setQty] = useState(1)
  const [idx, setIdx] = useState(0)
  const { data: p, isLoading, error, refetch } = useQuery({ queryKey: ['product', slug], retry: false, queryFn: () => api<Product>(`/products/${slug}/`) })

  if (isLoading) return <div className="container-x grid gap-10 py-10 md:grid-cols-2"><Skeleton className="aspect-[4/5]" /><Skeleton className="h-64" /></div>
  if (error instanceof ApiError && error.status === 404) return <Empty title="Product not found" text="This product may have been removed." action={<Link className="btn-primary" to="/shop">Back to shop</Link>} />
  if (error || !p) return <ErrorState onRetry={() => refetch()} />

  const inCart = cart.items.find((l) => l.product_id === p.id)?.quantity ?? 0
  const room = Math.max(p.stock_quantity - inCart, 0)
  const out = p.stock_status === 'out_of_stock'
  const img = p.images[idx]
  return (
    <div className="container-x py-8">
      <Link to="/shop" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-burgundy"><ArrowLeft size={16} aria-hidden /> Back to shop</Link>
      <div className="mt-6 grid gap-10 md:grid-cols-2">
        <div>
          <div className="overflow-hidden rounded-brand bg-blush/40"><Img src={img?.image} alt={img?.alt_text || p.name} eager /></div>
          {p.images.length > 1 && (
            <div className="mt-3 flex gap-2">{p.images.map((im, i) => (
              <button key={im.id} onClick={() => setIdx(i)} aria-label={`Show image ${i + 1}`} className={`w-16 overflow-hidden rounded-lg border-2 ${i === idx ? 'border-burgundy' : 'border-transparent'}`}><Img src={im.image} alt="" ratio="aspect-square" /></button>))}</div>
          )}
        </div>
        <div>
          {p.category && <p className="text-xs uppercase tracking-wider text-muted">{p.category.name}</p>}
          <h1 className="mt-1 text-4xl">{p.name}</h1>
          <p className="mt-3 text-2xl">{naira(p.price)}</p>
          <div className="mt-3 flex items-center gap-3"><StockBadge status={p.stock_status} />{!out && <span className="text-sm text-muted">{p.stock_quantity} available</span>}</div>
          <p className="mt-6 whitespace-pre-line leading-relaxed text-charcoal/80">{p.description || 'No description yet.'}</p>
          {!out && (
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <div className="flex items-center rounded-brand border border-taupe/50 bg-white" role="group" aria-label="Quantity">
                <button className="btn-ghost px-3" aria-label="Decrease quantity" onClick={() => setQty((q) => Math.max(1, q - 1))}><Minus size={16} /></button>
                <span className="w-10 text-center" aria-live="polite">{Math.min(qty, Math.max(room, 1))}</span>
                <button className="btn-ghost px-3" aria-label="Increase quantity" disabled={qty >= room} onClick={() => setQty((q) => q + 1)}><Plus size={16} /></button>
              </div>
              <button className="btn-primary flex-1 sm:flex-none sm:px-10" disabled={room < 1}
                onClick={async () => { try { await add(p.id, Math.min(qty, room)); toast(`${p.name} added to cart`); setQty(1) } catch (e: any) { toast(e.message, 'error') } }}>
                <ShoppingBag size={18} aria-hidden /> {room < 1 ? 'Maximum in cart' : 'Add to cart'}
              </button>
            </div>
          )}
          {inCart > 0 && <p className="mt-3 text-sm text-muted">{inCart} in your cart · <Link to="/cart" className="text-burgundy underline">view cart</Link></p>}
        </div>
      </div>
    </div>
  )
}
