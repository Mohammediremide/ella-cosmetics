import { Moon, Sun } from 'lucide-react'
import { useTheme } from '../lib/theme'

export default function ThemeToggle({ withLabel = false, className = '' }: { withLabel?: boolean; className?: string }) {
  const { theme, toggle } = useTheme()
  const dark = theme === 'dark'
  return (
    <button type="button" onClick={toggle} className={`btn-ghost px-3 ${className}`} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'} title={dark ? 'Light mode' : 'Dark mode'}>
      {dark ? <Sun size={20} aria-hidden /> : <Moon size={20} aria-hidden />}
      {withLabel && <span className="text-sm">{dark ? 'Light mode' : 'Dark mode'}</span>}
    </button>
  )
}
