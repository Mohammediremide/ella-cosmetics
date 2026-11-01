import { Component, type ReactNode } from 'react'

/** Last line of defence: if any page crashes, show a friendly screen instead of a blank page. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch(error: unknown) { console.error('Page crashed:', error) }
  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div role="alert" style={{ maxWidth: 440, margin: '18vh auto', padding: '0 24px', textAlign: 'center', fontFamily: 'system-ui, sans-serif' }}>
        <h1 style={{ fontSize: 28, color: '#632C3B', margin: 0 }}>Something went wrong</h1>
        <p style={{ color: '#6B5C58', lineHeight: 1.5 }}>We couldn’t show this page. Please refresh. If it keeps happening, contact the store.</p>
        <button onClick={() => window.location.reload()} style={{ background: '#632C3B', color: '#fff', border: 0, borderRadius: 12, padding: '12px 24px', fontSize: 15, cursor: 'pointer' }}>Refresh the page</button>
      </div>
    )
  }
}
