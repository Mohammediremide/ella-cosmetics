import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import ThemeToggle from '../components/ThemeToggle'

function mockSystem(dark: boolean) {
  window.matchMedia = vi.fn().mockImplementation((q: string) => ({ matches: q.includes('dark') && dark, media: q, addEventListener: vi.fn(), removeEventListener: vi.fn() })) as never
}
beforeEach(() => { localStorage.clear(); document.documentElement.removeAttribute('data-theme') })
afterEach(() => vi.restoreAllMocks())

describe('theme', () => {
  it('follows a dark system setting when nothing is saved', () => {
    mockSystem(true); render(<ThemeToggle />)
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(screen.getByRole('button', { name: 'Switch to light mode' })).toBeTruthy()
  })
  it('defaults to light for a light system setting', () => {
    mockSystem(false); render(<ThemeToggle />)
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })
  it('toggling switches the page theme and remembers the choice', () => {
    mockSystem(false); render(<ThemeToggle />)
    act(() => { fireEvent.click(screen.getByRole('button', { name: 'Switch to dark mode' })) })
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark'); expect(localStorage.getItem('ella_theme')).toBe('dark')
  })
  it('a saved choice beats the system setting', () => {
    mockSystem(true); localStorage.setItem('ella_theme', 'light'); render(<ThemeToggle />)
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })
  it('ignores a corrupted saved value', () => {
    mockSystem(false); localStorage.setItem('ella_theme', 'purple'); render(<ThemeToggle />)
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })
})
