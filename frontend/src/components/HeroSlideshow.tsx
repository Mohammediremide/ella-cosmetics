import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react'
import { assetUrl } from '../lib/api'
import type { Slide } from '../lib/types'

const IMAGE_MS = 6000
const prefersReducedMotion = () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** Homepage slideshow of admin-uploaded videos/images. Videos are muted (required for autoplay), play once each, then advance. */
export default function HeroSlideshow({ slides }: { slides: Slide[] }) {
  const [i, setI] = useState(0)
  const [paused, setPaused] = useState(prefersReducedMotion())  // WCAG: motion must be stoppable; off by default for reduced-motion users
  const videoRef = useRef<HTMLVideoElement>(null)
  const n = slides.length
  const idx = Math.min(i, n - 1)
  const slide = slides[idx]
  const next = useCallback(() => setI((v) => (v + 1) % n), [n])
  const prev = () => setI((v) => (v - 1 + n) % n)

  // images advance on a timer; videos advance when they finish
  useEffect(() => {
    if (paused || n < 2 || slide.media_type !== 'image') return
    const t = setTimeout(next, IMAGE_MS)
    return () => clearTimeout(t)
  }, [paused, n, slide, next])

  useEffect(() => {
    const v = videoRef.current
    if (!v) return
    v.muted = true  // React doesn't reliably set the muted attribute; autoplay requires it
    if (paused) v.pause(); else v.play()?.catch(() => {})  // play() may return nothing in older browsers
  }, [paused, slide])

  const hasText = slide.title || slide.subtitle || slide.button_label
  const link = slide.link_url
  const cta = slide.button_label && link
    ? (link.startsWith('/') ? <Link to={link} className="btn mt-5 bg-surface px-8 text-burgundy hover:bg-blush">{slide.button_label}</Link>
        : <a href={link} target="_blank" rel="noreferrer" className="btn mt-5 bg-surface px-8 text-burgundy hover:bg-blush">{slide.button_label}</a>)
    : null

  return (
    <section className="container-x pt-6 md:pt-10" aria-roledescription="carousel" aria-label="Featured from Ella Cosmetics">
      <h1 className="sr-only">Ella Cosmetics: discover your kind of beautiful</h1>
      <div className="relative overflow-hidden rounded-brand bg-charcoal">
        <div className="relative aspect-[4/5] sm:aspect-[16/9] lg:aspect-[21/9]" aria-live={paused ? 'polite' : 'off'}>
          {slide.media_type === 'video' && slide.video ? (
            <video key={slide.id} ref={videoRef} src={assetUrl(slide.video)} className="absolute inset-0 h-full w-full object-cover animate-[fade_.6s_ease]"
              muted playsInline preload="auto" autoPlay={!paused} loop={n === 1} onEnded={next} onError={() => n > 1 && next()} aria-label={slide.title || 'Promotional video'} />
          ) : (
            <img key={slide.id} src={assetUrl(slide.image)} alt={slide.title || 'Ella Cosmetics'} className="absolute inset-0 h-full w-full object-cover animate-[fade_.6s_ease]" />
          )}
          {hasText && (
            <div className="absolute inset-0 flex items-end bg-gradient-to-t from-charcoal/75 via-charcoal/25 to-transparent p-6 pb-16 text-white sm:items-center sm:bg-gradient-to-r sm:from-charcoal/70 sm:via-charcoal/20 sm:to-transparent sm:p-12">
              <div className="max-w-lg">
                {slide.title && <h2 className="text-4xl leading-tight sm:text-5xl lg:text-6xl">{slide.title}</h2>}
                {slide.subtitle && <p className="mt-3 text-base text-white/90 sm:text-lg">{slide.subtitle}</p>}
                {cta}
              </div>
            </div>
          )}
        </div>

        <div className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-3 p-3 sm:p-4">
          <button type="button" onClick={() => setPaused((p) => !p)} className="flex h-10 w-10 items-center justify-center rounded-full bg-surface/90 text-burgundy hover:bg-surface" aria-label={paused ? 'Play slideshow' : 'Pause slideshow'}>
            {paused ? <Play size={16} aria-hidden /> : <Pause size={16} aria-hidden />}
          </button>
          {n > 1 && (
            <>
              <div className="flex items-center gap-2" role="group" aria-label="Choose slide">
                {slides.map((s, k) => (
                  <button key={s.id} type="button" onClick={() => setI(k)} aria-label={`Slide ${k + 1} of ${n}`} aria-current={k === idx ? 'true' : undefined}
                    className="flex h-6 w-6 items-center justify-center"><span className={`block h-2.5 rounded-full transition-all ${k === idx ? 'w-7 bg-surface' : 'w-2.5 bg-surface/60'}`} /></button>))}
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={prev} className="flex h-10 w-10 items-center justify-center rounded-full bg-surface/90 text-burgundy hover:bg-surface" aria-label="Previous slide"><ChevronLeft size={18} aria-hidden /></button>
                <button type="button" onClick={next} className="flex h-10 w-10 items-center justify-center rounded-full bg-surface/90 text-burgundy hover:bg-surface" aria-label="Next slide"><ChevronRight size={18} aria-hidden /></button>
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  )
}
