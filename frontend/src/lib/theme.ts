import { useCallback, useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'
const KEY = 'ella_theme'
const systemPrefersDark = () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-color-scheme: dark)').matches
const stored = (): Theme | null => { try { const v = localStorage.getItem(KEY); return v === 'light' || v === 'dark' ? v : null } catch { return null } }
const apply = (t: Theme) => document.documentElement.setAttribute('data-theme', t)

/** Light/dark theme. Without a saved choice it follows the visitor's system setting (and keeps following it if that changes). */
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => stored() ?? (systemPrefersDark() ? 'dark' : 'light'))
  useEffect(() => { apply(theme) }, [theme])
  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!mq) return
    const h = (e: MediaQueryListEvent) => { if (!stored()) setThemeState(e.matches ? 'dark' : 'light') }
    mq.addEventListener('change', h)
    return () => mq.removeEventListener('change', h)
  }, [])
  const setTheme = useCallback((t: Theme) => { try { localStorage.setItem(KEY, t) } catch { /* private mode: still works for this visit */ } setThemeState(t) }, [])
  return { theme, setTheme, toggle: () => setTheme(theme === 'dark' ? 'light' : 'dark') }
}
