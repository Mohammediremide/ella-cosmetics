/** Brand tokens from the spec. */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: { ivory: '#FFF9F5', blush: '#F3DFE2', rose: '#C58C98', burgundy: '#632C3B', charcoal: '#292326', taupe: '#9B8A86', muted: '#6B5C58' },
      fontFamily: { serif: ['"DM Serif Display"', 'Georgia', 'serif'], sans: ['"DM Sans"', 'system-ui', 'sans-serif'] },
      boxShadow: { soft: '0 1px 2px rgba(41,35,38,.06), 0 4px 16px rgba(41,35,38,.06)' },
      borderRadius: { brand: '0.75rem' },
      keyframes: { fade: { from: { opacity: '0' }, to: { opacity: '1' } } },
    },
  },
  plugins: [],
}
