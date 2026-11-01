import { Link } from 'react-router-dom'
import { ShoppingBag } from 'lucide-react'
import { naira } from '../lib/api'
import { useCart } from '../lib/cart'
import { useToast } from '../lib/toast'
import type { Product } from '../lib/types'
import { Img, StockBadge } from './ui'

export default function ProductCard({ p }: { p: Product }) {
  const { add } = useCart()
  const toast = useToast()
  const out = p.stock_status === 'out_of_stock'
  return (
    <article className="group flex flex-col">
      <Link to={`/shop/${p.slug}`} className="relative block overflow-hidden rounded-brand bg-blush/40" aria-label={`View ${p.name}`}>
        <Img src={p.images[0]?.image} alt={p.images[0]?.alt_text || p.name} />
        {p.is_new && <span className="absolute left-3 top-3 rounded-full bg-burgundy px-2.5 py-0.5 text-[11px] font-semibold tracking-wider text-white">NEW</span>}
        {out && <div className="absolute inset-0 bg-surface/50" aria-hidden />}
      </Link>
      <div className="mt-3 flex flex-1 flex-col">
        {p.category && <p className="text-xs uppercase tracking-wider text-muted">{p.category.name}</p>}
        <h3 className="mt-0.5 font-sans text-base font-medium leading-snug"><Link to={`/shop/${p.slug}`} className="hover:text-burgundy">{p.name}</Link></h3>
        <div className="mt-1 flex items-center justify-between gap-2">
          <p className="font-medium">{naira(p.price)}</p><StockBadge status={p.stock_status} />
        </div>
        <button className="btn-outline mt-3 w-full" disabled={out}
          onClick={async () => { try { await add(p.id); toast(`${p.name} added to cart`) } catch (e: any) { toast(e.message, 'error') } }}>
          <ShoppingBag size={16} aria-hidden /> {out ? 'Unavailable' : 'Add to cart'}
        </button>
      </div>
    </article>
  )
}
