/** Brand tokens from the spec. */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // theme-aware (change in dark mode): see :root / [data-theme='dark'] in src/index.css
        ivory: 'rgb(var(--c-ivory) / <alpha-value>)', surface: 'rgb(var(--c-surface) / <alpha-value>)', blush: 'rgb(var(--c-blush) / <alpha-value>)',
        rose: 'rgb(var(--c-rose) / <alpha-value>)', burgundy: 'rgb(var(--c-burgundy) / <alpha-value>)', ink: 'rgb(var(--c-ink) / <alpha-value>)',
        muted: 'rgb(var(--c-muted) / <alpha-value>)', taupe: 'rgb(var(--c-taupe) / <alpha-value>)',
        // fixed brand colours (same in both themes: footer, overlays, text on photos)
        charcoal: '#292326', cream: '#FFF9F5',
      },
      fontFamily: { serif: ['"DM Serif Display"', 'Georgia', 'serif'], sans: ['"DM Sans"', 'system-ui', 'sans-serif'] },
      boxShadow: { soft: '0 1px 2px rgba(41,35,38,.06), 0 4px 16px rgba(41,35,38,.06)' },
      borderRadius: { brand: '0.75rem' },
      keyframes: { fade: { from: { opacity: '0' }, to: { opacity: '1' } } },
    },
  },
  plugins: [],
}
