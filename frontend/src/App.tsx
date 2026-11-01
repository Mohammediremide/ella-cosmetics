import { lazy, Suspense } from 'react'
import { Link } from 'react-router-dom'
import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { Empty, Skeleton } from './components/ui'
import Home from './pages/Home'
import Shop from './pages/Shop'
import ProductPage from './pages/ProductPage'
import CartPage from './pages/CartPage'
import Checkout from './pages/Checkout'
import OrderPage from './pages/OrderPage'
import Auth from './pages/Auth'
import { ForgotPassword, ResetPassword } from './pages/PasswordReset'
import Account from './pages/Account'
import Legal from './pages/Legal'

// Admin code is split out so customers never download it
const AdminLayout = lazy(() => import('./pages/admin/AdminLayout'))
const Overview = lazy(() => import('./pages/admin/Overview'))
const Products = lazy(() => import('./pages/admin/Products'))
const Sections = lazy(() => import('./pages/admin/Sections'))
const Customers = lazy(() => import('./pages/admin/Customers'))
const Slides = lazy(() => import('./pages/admin/Slides'))
const Payments = lazy(() => import('./pages/admin/Payments'))
const Orders = lazy(() => import('./pages/admin/Orders'))
const StoreSettings = lazy(() => import('./pages/admin/StoreSettings'))

export default function App() {
  return (
    <Suspense fallback={<div className="container-x py-10"><Skeleton className="h-64" /></div>}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="shop" element={<Shop />} />
          <Route path="shop/:slug" element={<ProductPage />} />
          <Route path="cart" element={<CartPage />} />
          <Route path="checkout" element={<Checkout />} />
          <Route path="orders/:reference" element={<OrderPage />} />
          <Route path="login" element={<Auth mode="login" />} />
          <Route path="register" element={<Auth mode="register" />} />
          <Route path="forgot-password" element={<ForgotPassword />} />
          <Route path="reset-password" element={<ResetPassword />} />
          <Route path="account" element={<Account />} />
          <Route path="privacy" element={<Legal kind="privacy" />} />
          <Route path="terms" element={<Legal kind="terms" />} />
          <Route path="*" element={<Empty title="Page not found" text="The page you’re looking for doesn’t exist or has moved." action={<Link className="btn-primary" to="/shop">Go to the shop</Link>} />} />
        </Route>
        <Route path="admin" element={<AdminLayout />}>
          <Route index element={<Overview />} />
          <Route path="products" element={<Products />} />
          <Route path="sections" element={<Sections />} />
          <Route path="categories" element={<Navigate to="/admin/sections" replace />} />
          <Route path="payments" element={<Payments />} />
          <Route path="slides" element={<Slides />} />
          <Route path="customers" element={<Customers />} />
          <Route path="orders" element={<Orders />} />
          <Route path="settings" element={<StoreSettings />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
