import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { Page, Product } from '../lib/types'
import ProductCard from '../components/ProductCard'
import { useCategories } from '../components/Layout'
import { EmptySection, ErrorState, Skeleton } from '../components/ui'

export default function Shop() {
  const [sp, setSp] = useSearchParams()
  const { data: cats = [], isSuccess: catsLoaded } = useCategories()
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); n.delete('page'); setSp(n) }
  const page = Number(sp.get('page') || 1)
  const qs = new URLSearchParams()
  for (const k of ['search', 'category', 'availability', 'ordering', 'featured', 'new']) if (sp.get(k)) qs.set(k, sp.get(k)!)
  qs.set('page', String(page))
  const { data, isLoading, isError, refetch, isFetching } = useQuery({ queryKey: ['products', qs.toString()], queryFn: () => api<Page<Product>>(`/products/?${qs}`), placeholderData: (p) => p })
  useEffect(() => { if (isError && page > 1) { const n = new URLSearchParams(sp); n.delete('page'); setSp(n, { replace: true }) } }, [isError]) // eslint-disable-line
  const pages = data ? Math.ceil(data.count / 12) : 1
  const slug = sp.get('category') ?? ''
  const section = cats.find((c) => c.slug === slug)
  const unknownSection = !!slug && catsLoaded && !section  // inactive, renamed-away or mistyped link
  const filtered = ['search', 'availability', 'featured', 'new'].some((k) => sp.get(k))
  const go = (n: number) => { const x = new URLSearchParams(sp); x.set('page', String(n)); setSp(x); window.scrollTo({ top: 0 }) }

  return (
    <div className="container-x py-10">
      <h1 className="text-4xl md:text-5xl">{section ? section.name : 'All Products'}</h1>
      <p className="mt-2 max-w-xl text-muted">{section?.description || 'Beauty essentials, thoughtfully selected.'} {data && !unknownSection && <span className="whitespace-nowrap">· {data.count} {data.count === 1 ? 'product' : 'products'}</span>}</p>
      <nav aria-label="Sections" className="-mx-4 mt-6 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:px-0">
        {[{ id: 0, name: 'All Products', slug: '' }, ...cats].map((c) => (
          <button key={c.id} onClick={() => set('category', c.slug)} aria-current={slug === c.slug ? 'true' : undefined}
            className={`min-h-[40px] shrink-0 rounded-full border px-4 text-sm transition-colors ${slug === c.slug ? 'border-burgundy bg-burgundy text-white' : 'border-taupe/50 bg-white hover:border-burgundy'}`}>{c.name}</button>))}
      </nav>
      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <input className="input" type="search" placeholder="Search products" aria-label="Search products" defaultValue={sp.get('search') ?? ''} onKeyDown={(e) => e.key === 'Enter' && set('search', e.currentTarget.value)} onBlur={(e) => e.currentTarget.value !== (sp.get('search') ?? '') && set('search', e.currentTarget.value)} />
        <select className="input" aria-label="Availability" value={sp.get('availability') ?? ''} onChange={(e) => set('availability', e.target.value)}>
          <option value="">Any availability</option><option value="in_stock">In stock</option><option value="out_of_stock">Out of stock</option>
        </select>
        <select className="input" aria-label="Sort" value={sp.get('ordering') ?? ''} onChange={(e) => set('ordering', e.target.value)}>
          <option value="">Newest</option><option value="price">Price: low to high</option><option value="-price">Price: high to low</option>
        </select>
      </div>

      <div className={`mt-8 transition-opacity ${isFetching && !isLoading ? 'opacity-60' : ''}`}>
        {unknownSection ? <EmptySection name={undefined} onAll={() => set('category', '')} />
          : isError ? <ErrorState onRetry={() => refetch()} />
          : isLoading ? <div className="grid grid-cols-2 gap-x-4 gap-y-8 md:grid-cols-3 lg:grid-cols-4">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="aspect-[4/5]" />)}</div>
          : !data?.results.length ? (filtered
              ? <div className="mx-auto max-w-sm py-14 text-center"><h2 className="text-2xl">No products match</h2><p className="mt-2 text-sm text-muted">Try a different search or clear your filters.</p><button className="btn-outline mt-5" onClick={() => { const n = new URLSearchParams(); if (slug) n.set('category', slug); setSp(n) }}>Clear filters</button></div>
              : <EmptySection name={section?.name} onAll={section ? () => set('category', '') : undefined} />)
          : <div className="grid grid-cols-2 gap-x-4 gap-y-8 md:grid-cols-3 lg:grid-cols-4">{data.results.map((p) => <ProductCard key={p.id} p={p} />)}</div>}
      </div>

      {pages > 1 && (
        <nav className="mt-12 flex items-center justify-center gap-4" aria-label="Pagination">
          <button className="btn-outline" disabled={page <= 1} onClick={() => go(page - 1)}>Previous</button>
          <span className="text-sm text-muted">Page {page} of {pages}</span>
          <button className="btn-outline" disabled={page >= pages} onClick={() => go(page + 1)}>Next</button>
        </nav>
      )}
    </div>
  )
}
