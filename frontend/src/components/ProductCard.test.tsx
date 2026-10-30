import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import ProductCard from './ProductCard'
import { renderAt } from '../test-utils'
import { AuthProvider } from '../lib/auth'
import { CartProvider } from '../lib/cart'
import type { Product } from '../lib/types'

const base: Product = { id: 1, name: 'Velvet Lipstick', slug: 'velvet-lipstick', description: '', price: '8500.00', category: { id: 1, name: 'Makeup', slug: 'makeup', image: null },
  images: [], stock_quantity: 5, stock_status: 'in_stock', is_new: true, is_featured: false, created_at: '' }
const show = (p: Product) => renderAt(<AuthProvider><CartProvider><ProductCard p={p} /></CartProvider></AuthProvider>)

describe('ProductCard', () => {
  it('shows name, naira price, section, NEW badge and an enabled add button', () => {
    show(base)
    expect(screen.getByText('Velvet Lipstick')).toBeTruthy(); expect(screen.getByText('₦8,500')).toBeTruthy()
    expect(screen.getByText('Makeup')).toBeTruthy(); expect(screen.getByText('NEW')).toBeTruthy()
    expect((screen.getByRole('button', { name: /add to cart/i }) as HTMLButtonElement).disabled).toBe(false)
  })
  it('disables purchase for out-of-stock products', () => {
    show({ ...base, stock_quantity: 0, stock_status: 'out_of_stock', is_new: false })
    expect((screen.getByRole('button', { name: /unavailable/i }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText('Out of stock')).toBeTruthy(); expect(screen.queryByText('NEW')).toBeNull()
  })
})
