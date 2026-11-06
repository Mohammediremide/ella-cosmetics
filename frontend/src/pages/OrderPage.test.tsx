import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import OrderPage from './OrderPage'
import { jsonResponse, renderAt } from '../test-utils'
import type { Order } from '../lib/types'

const order = (o: Partial<Order>): Order => ({
  reference: 'ELLA-ABCD2345', customer_name: 'Ada', customer_phone: '08031234567', delivery_method: 'pickup', delivery_address: '', note: '', subtotal: '25000', delivery_fee: '0', total: '25000.00',
  dispatch_requested: false, dispatch_address: '', dispatch_state: '', dispatch_city: '', dispatch_phone: '', dispatch_instructions: '', dispatch_status: '', dispatch_status_display: '',
  payment_status: 'awaiting_payment', payment_status_display: 'Awaiting Payment', payment_tone: 'awaiting_payment', payment_submitted_at: null, payment_reviewed_at: null, payment_rejection_reason: '',
  fulfilment_status: 'pending', fulfilment_status_display: 'Pending', items: [{ id: 1, product_name: 'Lip Tint', unit_price: '12500', quantity: 2, line_total: '25000' }], created_at: '2026-10-26T10:00:00Z',
  bank: { bank_name: 'Test Bank', account_name: 'Ella', account_number: '0123456789' },
  whatsapp_url: 'https://wa.me/2348088317529?text=hi', whatsapp_support_url: 'https://wa.me/2348088317529?text=help', ...o })
const show = (o: Order) => { vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(o)); return renderAt(<OrderPage />, `/orders/${o.reference}`, '/orders/:reference') }
afterEach(() => vi.restoreAllMocks())

describe('OrderPage payment states', () => {
  it('awaiting payment: bank details, the five steps, WhatsApp link and the Done button', async () => {
    show(order({}))
    await screen.findByText('Pay by bank transfer')
    expect(screen.getByText('0123456789')).toBeTruthy()
    expect(screen.getAllByRole('listitem').length).toBeGreaterThanOrEqual(5)
    expect((screen.getByRole('link', { name: /send receipt on whatsapp/i }) as HTMLAnchorElement).href).toBe('https://wa.me/2348088317529?text=hi')
    expect(screen.getByRole('button', { name: /Done — I’ve Sent the Receipt/ })).toBeTruthy()
  })
  it('pending verification: explains the wait, no Done button, never says paid', async () => {
    show(order({ payment_status: 'pending_verification', payment_status_display: 'Processing — Awaiting Verification', payment_tone: 'pending_verification', payment_submitted_at: '2026-10-26T10:05:00Z' }))
    await waitFor(() => expect(screen.getAllByText('Processing — Awaiting Verification').length).toBeGreaterThan(0))
    expect(screen.queryByRole('button', { name: /Done —/ })).toBeNull()
    expect(screen.queryByText('Payment Successful')).toBeNull()
    expect(screen.getByRole('link', { name: /reopen whatsapp/i })).toBeTruthy()
  })
  it('rejected: shows the admin reason and a WhatsApp help link, and allows resubmitting', async () => {
    show(order({ payment_status: 'rejected', payment_status_display: 'Payment Rejected', payment_tone: 'rejected', payment_rejection_reason: 'Only ₦20,000 arrived' }))
    await screen.findByText(/Only ₦20,000 arrived/)
    expect((screen.getByRole('link', { name: /contact ella cosmetics on whatsapp/i }) as HTMLAnchorElement).href).toContain('wa.me/2348088317529')
    expect(screen.getByRole('button', { name: /Done —/ })).toBeTruthy()
  })
  it('verified: success panel, no payment instructions, fulfilment shown separately', async () => {
    show(order({ payment_status: 'verified', payment_status_display: 'Payment Successful', payment_tone: 'verified', bank: null, fulfilment_status: 'processing', fulfilment_status_display: 'Processing' }))
    await waitFor(() => expect(screen.getAllByText('Payment Successful').length).toBeGreaterThan(0))
    expect(screen.queryByText('Pay by bank transfer')).toBeNull()
    expect(screen.getByText(/doesn’t mean delivered/)).toBeTruthy()
  })
  it('cancelled: no payment actions', async () => {
    show(order({ fulfilment_status: 'cancelled', fulfilment_status_display: 'Cancelled', payment_tone: 'cancelled', payment_status_display: 'Cancelled', bank: null }))
    await screen.findByText(/This order was cancelled/)
    expect(screen.queryByRole('button', { name: /Done —/ })).toBeNull()
  })
  it('shows dispatch progress only for orders that requested dispatch', async () => {
    show(order({ dispatch_requested: true, dispatch_address: '1 Main Street', dispatch_state: 'Lagos', dispatch_city: 'Ikeja', dispatch_phone: '08011111111', dispatch_status: 'dispatched', dispatch_status_display: 'Dispatched' }))
    await screen.findByText('Dispatch delivery tracking')
    expect(screen.getByText('1 Main Street')).toBeTruthy()
    const currentStage = screen.getAllByRole('listitem').find((item) => item.textContent?.includes('Dispatched'))
    expect(currentStage?.getAttribute('aria-current')).toBe('step')
  })
})
