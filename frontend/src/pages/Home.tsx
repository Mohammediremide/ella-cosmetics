import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight } from 'lucide-react'
import { api, assetUrl } from '../lib/api'
import type { Category, Page, Product } from '../lib/types'
import ProductCard from '../components/ProductCard'
import { useCategories } from '../components/Layout'
import HeroSlideshow from '../components/HeroSlideshow'
import { Skeleton } from '../components/ui'
import type { Slide } from '../lib/types'

const useProducts = (q: string) => useQuery({ queryKey: ['products', 'home', q], queryFn: () => api<Page<Product>>(`/products/?${q}`) })

function Row({ title, to, q }: { title: string; to: string; q: string }) {
  const { data, isLoading } = useProducts(q)
  if (isLoading) return <section className="container-x mt-20"><Skeleton className="h-8 w-48" /><div className="mt-8 grid grid-cols-2 gap-x-4 gap-y-8 lg:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="aspect-[4/5]" />)}</div></section>
  if (!data?.results.length) return null  // no empty headings, no fake products
  return (
    <section className="container-x mt-20">
      <div className="mb-8 flex items-end justify-between"><h2 className="text-3xl md:text-4xl">{title}</h2><Link to={to} className="text-sm text-burgundy underline-offset-4 hover:underline">View all</Link></div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-8 lg:grid-cols-4">{data.results.slice(0, 4).map((p) => <ProductCard key={p.id} p={p} />)}</div>
    </section>
  )
}

function SectionCard({ c, i }: { c: Category; i: number }) {
  const tint = ['from-blush to-rose/60', 'from-rose/40 to-blush', 'from-blush/80 to-burgundy/30'][i % 3]
  return (
    <Link to={`/shop?category=${c.slug}`} className="group relative block overflow-hidden rounded-brand bg-blush focus-visible:outline-offset-4">
      {c.image
        ? <img src={assetUrl(c.image)} alt="" loading="lazy" className="aspect-[4/5] w-full object-cover transition-transform duration-500 group-hover:scale-[1.03] sm:aspect-[4/3] md:aspect-[4/5]" />
        : <div className={`flex aspect-[4/5] w-full items-center justify-center bg-gradient-to-br ${tint} sm:aspect-[4/3] md:aspect-[4/5]`} aria-hidden><span className="font-serif text-7xl text-burgundy/25">{c.name[0]}</span></div>}
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-charcoal/80 via-charcoal/40 to-transparent p-5 pt-16 text-white">
        <h3 className="text-2xl">{c.name}</h3>
        <p className="mt-1 flex items-center justify-between text-sm text-white/90">
          <span>{c.product_count ? `${c.product_count} ${c.product_count === 1 ? 'product' : 'products'}` : 'Coming soon'}</span>
          <span className="flex items-center gap-1 font-medium">Shop <ArrowRight size={14} aria-hidden className="transition-transform group-hover:translate-x-1" /></span>
        </p>
      </div>
    </Link>
  )
}

export default function Home() {
  const { data: cats = [], isLoading: catsLoading } = useCategories()
  const { data: slides = [], isLoading: slidesLoading } = useQuery({ queryKey: ['slides'], staleTime: 60_000, queryFn: () => api<Slide[]>('/slides/') })
  return (
    <>
      {slidesLoading ? <div className="container-x pt-10"><Skeleton className="aspect-[4/5] sm:aspect-[16/9] lg:aspect-[21/9]" /></div>
        : slides.length > 0 ? <HeroSlideshow slides={slides} />
        : (
      <section className="container-x grid items-center gap-10 py-12 md:grid-cols-12 md:py-20">
        <div className="md:col-span-6 lg:col-span-5">
          <p className="text-xs font-medium tracking-[0.25em] text-burgundy">YOUR BEAUTY, YOUR WAY</p>
          <h1 className="mt-4 text-5xl leading-[1.05] text-burgundy md:text-6xl lg:text-7xl">Discover your kind of beautiful.</h1>
          <p className="mt-5 max-w-md text-lg text-ink/80">Explore beauty essentials selected to help you express yourself with confidence.</p>
          <div className="mt-8 flex flex-wrap gap-3"><Link to="/shop" className="btn-primary px-8">Shop All Products</Link>{cats[0] && <a href="#categories" className="btn-outline px-8">Shop by Category</a>}</div>
        </div>
        <div className="md:col-span-6 lg:col-span-7">
          <div className="relative flex aspect-[4/3] items-center justify-center overflow-hidden rounded-brand bg-gradient-to-br from-blush via-ivory to-rose/50 md:aspect-[5/4]" aria-hidden>
            <div className="absolute inset-6 rounded-brand border border-burgundy/20" /><span className="font-serif text-8xl text-burgundy/30 md:text-9xl">Ella</span></div>
        </div>
      </section>
        )}

      <section id="categories" className="container-x mt-8 scroll-mt-24" aria-labelledby="cat-h">
        <div className="mb-8 flex items-end justify-between"><h2 id="cat-h" className="text-3xl md:text-4xl">Shop by Category</h2><Link to="/shop" className="text-sm text-burgundy underline-offset-4 hover:underline">All Products</Link></div>
        {catsLoading ? <div className="grid gap-4 sm:grid-cols-3">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="aspect-[4/5]" />)}</div>
          : !cats.length ? <p className="rounded-brand bg-blush/40 p-6 text-center text-sm text-muted">Sections will appear here once they’re added.</p>
          : <div className={`grid grid-cols-1 gap-4 sm:grid-cols-2 ${cats.length === 4 ? "lg:grid-cols-4" : "lg:grid-cols-3"}`}>{cats.map((c, i) => <SectionCard key={c.id} c={c} i={i} />)}</div>}
      </section>

      <Row title="Featured" to="/shop?featured=true" q="featured=true" />
      <Row title="New arrivals" to="/shop?new=true" q="new=true" />

      <section className="container-x mt-24 text-center">
        <p className="mx-auto max-w-3xl font-serif text-3xl leading-snug text-burgundy md:text-4xl">“Beauty essentials for every day, every mood, and every version of you.”</p>
      </section>
    </>
  )
}
