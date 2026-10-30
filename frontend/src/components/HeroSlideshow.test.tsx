import { describe, expect, it } from 'vitest'
import { fireEvent, screen } from '@testing-library/react'
import HeroSlideshow from './HeroSlideshow'
import { renderAt } from '../test-utils'
import type { Slide } from '../lib/types'

const mk = (id: number, o: Partial<Slide> = {}): Slide => ({ id, title: `Slide ${id}`, subtitle: '', button_label: '', link_url: '', media_type: 'image', video: null, image: `/media/s${id}.png`, ...o })

describe('HeroSlideshow', () => {
  it('shows the first slide with text and a button that links to a site page', () => {
    renderAt(<HeroSlideshow slides={[mk(1, { button_label: 'Shop makeup', link_url: '/shop?category=makeup' }), mk(2)]} />)
    expect(screen.getByRole('heading', { name: 'Slide 1' })).toBeTruthy()
    expect((screen.getByRole('link', { name: 'Shop makeup' }) as HTMLAnchorElement).getAttribute('href')).toBe('/shop?category=makeup')
  })
  it('next / previous / dots change the slide and wrap around', () => {
    renderAt(<HeroSlideshow slides={[mk(1), mk(2), mk(3)]} />)
    fireEvent.click(screen.getByRole('button', { name: 'Next slide' })); expect(screen.getByRole('heading', { name: 'Slide 2' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Previous slide' })); fireEvent.click(screen.getByRole('button', { name: 'Previous slide' }))
    expect(screen.getByRole('heading', { name: 'Slide 3' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Slide 1 of 3' })); expect(screen.getByRole('heading', { name: 'Slide 1' })).toBeTruthy()
  })
  it('renders a muted, inline video for video slides and offers pause/play', () => {
    const { container } = renderAt(<HeroSlideshow slides={[mk(1, { media_type: 'video', video: '/media/a.mp4', image: null })]} />)
    const v = container.querySelector('video')!
    expect(v.getAttribute('src')).toBe('/media/a.mp4'); expect(v.hasAttribute('playsinline')).toBe(true); expect(v.loop).toBe(true)
    const btn = screen.getByRole('button', { name: /pause slideshow/i }); fireEvent.click(btn)
    expect(screen.getByRole('button', { name: /play slideshow/i })).toBeTruthy()
  })
  it('a single slide has no next/previous controls', () => {
    renderAt(<HeroSlideshow slides={[mk(1)]} />)
    expect(screen.queryByRole('button', { name: 'Next slide' })).toBeNull()
  })
})
