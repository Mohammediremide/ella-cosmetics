import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link } from 'react-router-dom'
import { History, Pencil, Plus, RefreshCw, Trash2, Upload } from 'lucide-react'
import { api, ApiError, fieldError, naira } from '../../lib/api'
import { useToast } from '../../lib/toast'
import type { Category, Page, Product } from '../../lib/types'
import { Empty, Field, Img, Modal, Pager, Skeleton, StockBadge } from '../../components/ui'

const schema = z.object({
  name: z.string().trim().min(2, 'Enter a product name'), description: z.string().optional(),
  price: z.coerce.number({ invalid_type_error: 'Enter a price' }).min(0, 'Price cannot be negative'),
  stock_quantity: z.coerce.number().int('Whole numbers only').min(0, 'Stock cannot be negative'),
  low_stock_threshold: z.union([z.literal(''), z.coerce.number().int().min(0)]).optional(),
  category_id: z.string().min(1, 'Choose a section for this product'), is_featured: z.boolean(), is_new_arrival: z.boolean(), is_upcoming: z.boolean(), is_active: z.boolean(),
})
type F = z.infer<typeof schema>

function ProductForm({ product, cats, onDone }: { product: Product | null; cats: Category[]; onDone: () => void }) {
  const qc = useQueryClient(), toast = useToast()
  const [err, setErr] = useState<unknown>(null)
  const [current, setCurrent] = useState<Product | null>(product)
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<F>({
    resolver: zodResolver(schema) as any,
    defaultValues: { name: product?.name ?? '', description: product?.description ?? '', price: product ? Number(product.price) : ('' as any), stock_quantity: product?.stock_quantity ?? 0,
      low_stock_threshold: (product?.low_stock_threshold ?? '') as any, category_id: product?.category ? String(product.category.id) : '', is_featured: product?.is_featured ?? false, is_new_arrival: product?.is_new_arrival ?? false, is_upcoming: product?.is_upcoming ?? false, is_active: product?.is_active ?? true },
  })
  const sections = cats.filter((c) => c.is_active || c.id === product?.category?.id)  // inactive sections can't receive products
  const refresh = () => qc.invalidateQueries({ queryKey: ['admin'] })
  const save = handleSubmit(async (d) => {
    setErr(null)
    const body = { ...d, category_id: d.category_id ? Number(d.category_id) : null, low_stock_threshold: d.low_stock_threshold === '' ? null : d.low_stock_threshold }
    try {
      const saved = await api<Product>(current ? `/admin/products/${current.id}/` : '/admin/products/', { method: current ? 'PATCH' : 'POST', body })
      qc.invalidateQueries({ queryKey: ['products'] }); refresh(); toast('Product saved')
      if (!current) { setCurrent(saved); toast('Now you can add images', 'info') } else onDone()
    } catch (e) { setErr(e); toast(e instanceof ApiError ? e.message : 'Save failed', 'error') }
  })
  const reload = async () => { if (current) setCurrent(await api<Product>(`/admin/products/${current.id}/`)); refresh(); qc.invalidateQueries({ queryKey: ['products'] }) }
  const upload = async (f: File | undefined) => {
    if (!f || !current) return
    const form = new FormData(); form.append('image', f); form.append('alt_text', current.name)
    try { await api(`/admin/products/${current.id}/images/`, { method: 'POST', form }); await reload(); toast('Image uploaded') } catch (e) { toast(e instanceof ApiError ? (fieldError(e, 'image') ?? e.message) : 'Upload failed', 'error') }
  }
  const replaceImg = async (id: number, f: File | undefined) => {
    if (!f) return
    const form = new FormData(); form.append('image', f)
    try { await api(`/admin/product-images/${id}/`, { method: 'PATCH', form }); await reload(); toast('Image replaced') } catch (e) { toast(e instanceof ApiError ? (fieldError(e, 'image') ?? e.message) : 'Replace failed', 'error') }
  }
  const delImg = async (id: number) => { await api(`/admin/product-images/${id}/`, { method: 'DELETE' }); await reload(); toast('Image removed') }
  const fe = (n: string, m?: string) => m ?? fieldError(err, n)

  return (
    <form onSubmit={save} noValidate className="space-y-4">
      <Field label="Name" htmlFor="pn" error={fe('name', errors.name?.message)}><input id="pn" className="input" {...register('name')} /></Field>
      <Field label="Description" htmlFor="pd"><textarea id="pd" rows={4} className="input py-3" {...register('description')} /></Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Price (₦)" htmlFor="pp" error={fe('price', errors.price?.message)}><input id="pp" inputMode="decimal" className="input" {...register('price')} /></Field>
        <Field label="Section" htmlFor="pc" error={fe('category_id', errors.category_id?.message)}>
          {sections.length === 0 ? (
            <p className="rounded-brand bg-amber-50 p-3 text-sm text-amber-900">No sections available. <Link className="font-medium underline" to="/admin/sections">Create a section first</Link>, then come back to add this product.</p>
          ) : (
            <select id="pc" className="input" {...register('category_id')}><option value="">Select a section…</option>
              {sections.map((c) => <option key={c.id} value={c.id} disabled={!c.is_active && c.id !== product?.category?.id}>{c.name}{!c.is_active ? ' (inactive)' : ''}</option>)}</select>)}
        </Field>
        <Field label="Stock quantity" htmlFor="ps" error={fe('stock_quantity', errors.stock_quantity?.message)}><input id="ps" inputMode="numeric" className="input" {...register('stock_quantity')} /></Field>
        <Field label="Low-stock threshold (blank = store default)" htmlFor="pt"><input id="pt" inputMode="numeric" className="input" {...register('low_stock_threshold')} /></Field>
      </div>
      <div className="flex flex-wrap gap-5 text-sm">
        {([['is_active', 'Active (visible in store)'], ['is_featured', 'Featured'], ['is_new_arrival', 'Always show NEW badge'], ['is_upcoming', 'Upcoming (Coming Soon; not purchasable)']] as const).map(([k, l]) => <label key={k} className="flex min-h-[44px] items-center gap-2"><input type="checkbox" className="h-4 w-4 accent-burgundy" {...register(k)} /> {l}</label>)}
      </div>

      <div>
        <p className="label">Images</p>
        {!current ? <p className="text-sm text-muted">Save the product first, then add images.</p> : (
          <div className="flex flex-wrap gap-3">
            {current.images.map((im) => (
              <div key={im.id} className="relative w-24 overflow-hidden rounded-brand"><Img src={im.image} alt={im.alt_text || current.name} ratio="aspect-square" />
                <button type="button" onClick={() => delImg(im.id)} aria-label="Remove image" className="absolute right-1 top-1 rounded-full bg-surface/90 p-1.5 text-burgundy"><Trash2 size={14} /></button>
                <label className="absolute bottom-1 left-1 cursor-pointer rounded-full bg-surface/90 p-1.5 text-burgundy" title="Replace image"><RefreshCw size={14} aria-hidden /><span className="sr-only">Replace image</span>
                  <input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={(e) => { replaceImg(im.id, e.target.files?.[0]); e.target.value = '' }} /></label></div>))}
            <label className="flex aspect-square w-24 cursor-pointer flex-col items-center justify-center gap-1 rounded-brand border border-dashed border-taupe text-xs text-muted hover:border-burgundy hover:text-burgundy">
              <Upload size={18} aria-hidden /> Add<input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={(e) => { upload(e.target.files?.[0]); e.target.value = '' }} /></label>
          </div>)}
        <p className="mt-2 text-xs text-muted">JPEG, PNG or WebP, up to 5 MB.</p>
      </div>
      <div className="flex justify-end gap-3 pt-2"><button type="button" className="btn-ghost" onClick={onDone}>Close</button><button className="btn-primary" disabled={isSubmitting || sections.length === 0}>{isSubmitting ? 'Saving…' : 'Save product'}</button></div>
    </form>
  )
}

function StockModal({ product, onClose }: { product: Product | null; onClose: () => void }) {
  const qc = useQueryClient(), toast = useToast()
  const [delta, setDelta] = useState(''), [reason, setReason] = useState(''), [err, setErr] = useState<unknown>(null)
  const { data: hist = [] } = useQuery({ queryKey: ['admin', 'stock', product?.id], enabled: !!product, queryFn: () => api<any[]>(`/admin/products/${product!.id}/stock-history/`) })
  const adjust = useMutation({
    mutationFn: () => api<Product>(`/admin/products/${product!.id}/adjust-stock/`, { method: 'POST', body: { delta: Number(delta), reason } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin'] }); qc.invalidateQueries({ queryKey: ['products'] }); setDelta(''); setReason(''); setErr(null); toast('Stock updated') },
    onError: (e) => { setErr(e); toast(e instanceof ApiError ? e.message : 'Update failed', 'error') },
  })
  return (
    <Modal open={!!product} title={product ? `Stock · ${product.name}` : ''} onClose={onClose}>
      <p className="text-sm">In stock now: <strong>{hist[0]?.resulting_quantity ?? product?.stock_quantity}</strong></p>
      <form className="mt-3 grid grid-cols-[6rem_1fr_auto] items-end gap-2" onSubmit={(e) => { e.preventDefault(); adjust.mutate() }}>
        <Field label="Change (+/−)" htmlFor="sd1" error={fieldError(err, 'delta')}><input id="sd1" className="input" inputMode="numeric" value={delta} onChange={(e) => setDelta(e.target.value.replace(/[^0-9-]/g, ''))} placeholder="+10" /></Field>
        <Field label="Reason" htmlFor="sd2" error={fieldError(err, 'reason')}><input id="sd2" className="input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. New delivery" /></Field>
        <button className="btn-primary" disabled={adjust.isPending || !delta || delta === '-' || !reason.trim()}>Apply</button>
      </form>
      <h3 className="mt-5 font-sans text-sm font-semibold">History</h3>
      <ul className="mt-2 max-h-56 divide-y divide-taupe/15 overflow-y-auto text-xs">
        {hist.map((h, i) => <li key={i} className="flex justify-between gap-3 py-2"><span><strong className={h.delta < 0 ? 'text-red-700' : 'text-emerald-700'}>{h.delta > 0 ? '+' : ''}{h.delta}</strong> → {h.resulting_quantity} · {h.reason || h.kind}<span className="block text-muted">{h.by ?? 'system / customer order'}</span></span><span className="shrink-0 text-muted">{new Date(h.created_at).toLocaleString('en-NG', { dateStyle: 'short', timeStyle: 'short' })}</span></li>)}
        {!hist.length && <li className="py-3 text-muted">No changes recorded yet.</li>}
      </ul>
      <div className="mt-4 flex justify-end"><button className="btn-ghost" onClick={onClose}>Close</button></div>
    </Modal>
  )
}

export default function Products() {
  const qc = useQueryClient(), toast = useToast()
  const [search, setSearch] = useState(''), [sectionFilter, setSectionFilter] = useState(''), [page, setPage] = useState(1)
  const [stockFor, setStockFor] = useState<Product | null>(null)
  const [editing, setEditing] = useState<Product | 'new' | null>(null)
  const [confirm, setConfirm] = useState<Product | null>(null)
  const { data, isLoading } = useQuery({ queryKey: ['admin', 'products', search, sectionFilter, page], queryFn: () => api<Page<Product>>(`/admin/products/?search=${encodeURIComponent(search)}&page=${page}${sectionFilter ? `&category=${sectionFilter}` : ''}`) })
  const { data: cats = [] } = useQuery({ queryKey: ['admin', 'categories'], queryFn: () => api<Category[]>('/admin/categories/') })
  const archive = useMutation({ mutationFn: (p: Product) => api(`/admin/products/${p.id}/`, { method: 'DELETE' }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin'] }); qc.invalidateQueries({ queryKey: ['products'] }); toast('Product archived'); setConfirm(null) } })
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-4xl">Products</h1><button className="btn-primary" onClick={() => setEditing('new')}><Plus size={18} aria-hidden /> New product</button></div>
      <div className="mt-5 flex flex-wrap gap-3">
        <input className="input max-w-sm" type="search" placeholder="Search products" aria-label="Search products" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }} />
        <select className="input max-w-[14rem]" aria-label="Filter by section" value={sectionFilter} onChange={(e) => { setSectionFilter(e.target.value); setPage(1) }}><option value="">All sections</option>{cats.map((c) => <option key={c.id} value={c.slug}>{c.name}</option>)}</select>
      </div>
      <div className="card mt-4 overflow-x-auto">
        {isLoading ? <Skeleton className="h-48" /> : !data?.results.length ? <Empty title="No products yet" text="Create your first product to see it in the store." /> : (
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-taupe/20 text-xs uppercase tracking-wider text-muted"><tr><th className="p-3">Product</th><th>Section</th><th>Price</th><th>Stock</th><th>Status</th><th className="pr-3 text-right">Actions</th></tr></thead>
            <tbody className="divide-y divide-taupe/15">{data.results.map((p) => (
              <tr key={p.id} className={p.is_active ? '' : 'opacity-50'}>
                <td className="flex items-center gap-3 p-3"><div className="w-10 overflow-hidden rounded-lg"><Img src={p.images[0]?.image} alt="" ratio="aspect-square" /></div><span className="font-medium">{p.name}{p.is_upcoming && ' (upcoming)'}{!p.is_active && ' (archived)'}</span></td>
                <td>{p.category ? <>{p.category.name}{p.category.is_active === false && <span className="ml-1 text-xs text-muted">(inactive)</span>}</> : <span className="text-muted">—</span>}</td><td>{naira(p.price)}</td><td>{p.stock_quantity}</td><td><StockBadge status={p.stock_status} /></td>
                <td className="pr-3 text-right"><button className="btn-ghost px-3" aria-label={`Stock history for ${p.name}`} onClick={() => setStockFor(p)}><History size={16} /></button><button className="btn-ghost px-3" aria-label={`Edit ${p.name}`} onClick={() => setEditing(p)}><Pencil size={16} /></button>
                  {p.is_active && <button className="btn-ghost px-3" aria-label={`Archive ${p.name}`} onClick={() => setConfirm(p)}><Trash2 size={16} /></button>}</td></tr>))}</tbody>
          </table>)}
        <Pager page={page} count={data?.count ?? 0} onPage={setPage} />
      </div>
      <StockModal product={stockFor} onClose={() => setStockFor(null)} />
      {editing && <div className="fixed inset-0 z-50 flex items-end justify-center overflow-y-auto bg-charcoal/50 p-0 sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label="Product form">
        <div className="card my-auto w-full max-w-2xl p-6"><h2 className="mb-4 text-2xl">{editing === 'new' ? 'New product' : 'Edit product'}</h2><ProductForm product={editing === 'new' ? null : editing} cats={cats} onDone={() => setEditing(null)} /></div></div>}
      <Modal open={!!confirm} title="Archive product?" onClose={() => setConfirm(null)}>
        <p className="text-sm">“{confirm?.name}” will disappear from the store. Past orders keep their records. You can re-activate it later by editing it.</p>
        <div className="mt-5 flex justify-end gap-3"><button className="btn-ghost" onClick={() => setConfirm(null)}>Cancel</button><button className="btn-primary" onClick={() => confirm && archive.mutate(confirm)}>Archive</button></div>
      </Modal>
    </div>
  )
}
