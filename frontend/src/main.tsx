import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import ErrorBoundary from './components/ErrorBoundary'
import { AuthProvider } from './lib/auth'
import { CartProvider } from './lib/cart'
import { ToastProvider } from './lib/toast'
import '@fontsource/dm-sans/400.css'
import '@fontsource/dm-sans/500.css'
import '@fontsource/dm-sans/600.css'
import '@fontsource/dm-serif-display/400.css'  // self-hosted fonts: no third-party requests
import './index.css'

// ~30 s of patience with back-off: Render's free plan sleeps when idle and takes up to a minute to wake
const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: 5, retryDelay: (n) => Math.min(1000 * 2 ** n, 10_000) } } })

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <ToastProvider><AuthProvider><CartProvider><App /></CartProvider></AuthProvider></ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>,
)
