import { Link } from 'react-router-dom'
import { Minus, Plus, Trash2 } from 'lucide-react'
import { naira } from '../lib/api'
import { useCart } from '../lib/cart'
import { useToast } from '../lib/toast'
import { Empty, Img, Skeleton } from '../components/ui'

export default function CartPage() {
  const { cart, setQuantity, remove, loading } = useCart()
  const toast = useToast()
  const run = (f: () => Promise<void>) => f().catch((e) => toast(e.message, 'error'))
  if (loading && !cart.items.length) return <div className="container-x py-10"><Skeleton className="h-64" /></div>
  if (!cart.items.length) return <Empty title="Your cart is empty" text="Find something you’ll love." action={<Link to="/shop" className="btn-primary">Continue shopping</Link>} />
  return (
    <div className="container-x grid gap-10 py-10 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <h1 className="text-4xl">Your cart</h1>
        <ul className="mt-6 divide-y divide-taupe/20">
          {cart.items.map((l) => (
            <li key={l.product_id} className="flex gap-4 py-5">
              <Link to={`/shop/${l.slug}`} className="w-24 shrink-0 overflow-hidden rounded-brand"><Img src={l.image} alt={l.name} ratio="aspect-square" /></Link>
              <div className="flex flex-1 flex-col justify-between">
                <div className="flex justify-between gap-3">
                  <div><Link to={`/shop/${l.slug}`} className="font-medium hover:text-burgundy">{l.name}</Link><p className="text-sm text-muted">{naira(l.unit_price)} each</p></div>
                  <p className="font-medium">{naira(l.line_total)}</p>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center rounded-brand border border-taupe/40" role="group" aria-label={`Quantity for ${l.name}`}>
                    <button className="btn-ghost px-3" aria-label="Decrease" onClick={() => run(() => setQuantity(l.product_id, l.quantity - 1))}><Minus size={14} /></button>
                    <span className="w-8 text-center text-sm">{l.quantity}</span>
                    <button className="btn-ghost px-3" aria-label="Increase" disabled={l.quantity >= l.available} onClick={() => run(() => setQuantity(l.product_id, l.quantity + 1))}><Plus size={14} /></button>
                  </div>
                  <button className="btn-ghost px-3 text-sm text-muted" onClick={() => run(() => remove(l.product_id))}><Trash2 size={16} aria-hidden /> Remove</button>
                </div>
              </div>
            </li>
          ))}
        </ul>
        <Link to="/shop" className="mt-4 inline-block text-sm text-burgundy underline-offset-4 hover:underline">← Continue shopping</Link>
      </div>
      <aside className="card h-fit p-6 lg:sticky lg:top-24">
        <h2 className="text-2xl">Order summary</h2>
        <dl className="mt-4 space-y-2 text-sm"><div className="flex justify-between"><dt>Subtotal</dt><dd>{naira(cart.subtotal)}</dd></div><div className="flex justify-between text-muted"><dt>Delivery</dt><dd>Calculated at checkout</dd></div></dl>
        <Link to="/checkout" className="btn-primary mt-6 w-full">Checkout</Link>
        <p className="mt-3 text-xs text-muted">Prices and availability are confirmed again when you place your order.</p>
      </aside>
    </div>
  )
}
