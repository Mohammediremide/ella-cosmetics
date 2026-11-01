export interface Category {
  id: number; name: string; slug: string; description?: string; image: string | null
  product_count?: number; total_products?: number; is_active?: boolean; sort_order?: number
}
export interface ProductImage { id: number; image: string; alt_text: string }
export interface Product {
  id: number; name: string; slug: string; description: string; price: string; category: Category | null
  images: ProductImage[]; stock_quantity: number; stock_status: 'in_stock' | 'low_stock' | 'out_of_stock'
  is_new: boolean; is_featured: boolean; created_at: string
  is_active?: boolean; is_new_arrival?: boolean; low_stock_threshold?: number | null
}
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
export interface User { id: number; name: string; email: string; phone: string; is_staff: boolean }
export interface CartLine { product_id: number; slug: string; name: string; image: string | null; unit_price: string; quantity: number; line_total: string; available: number }
export interface CartData { items: CartLine[]; subtotal: number | string; adjusted: boolean }
export interface PublicSettings {
  store_name: string; announcement: string; contact_email: string; contact_phone: string; instagram_url: string; whatsapp_number: string
  currency_symbol: string; delivery_enabled: boolean; pickup_enabled: boolean; delivery_fee: string; pickup_instructions: string
  password_reset_enabled: boolean; legal_business_name: string; business_address: string; delivery_terms: string; returns_terms: string; unpaid_order_hours: number
}
export interface OrderItem { id: number; product_name: string; unit_price: string; quantity: number; line_total: string }
export interface Order {
  id?: number; reference: string; customer_name: string; customer_phone: string; delivery_method: 'delivery' | 'pickup'; delivery_address: string; note: string
  subtotal: string; delivery_fee: string; total: string; payment_status: string; payment_status_display: string; payment_tone: string
  payment_submitted_at: string | null; payment_reviewed_at: string | null; payment_rejection_reason: string
  fulfilment_status: string; fulfilment_status_display: string; items: OrderItem[]; created_at: string
  bank: { bank_name: string; account_name: string; account_number: string } | null; whatsapp_url: string; whatsapp_support_url: string
  payment_reviewed_by?: string | null; customer_whatsapp_url?: string
  customer_email?: string; item_count?: number; audit?: { field: string; from: string; to: string; by: string; at: string; note: string }[]
}

export interface Slide {
  id: number; title: string; subtitle: string; button_label: string; link_url: string
  media_type: 'video' | 'image'; video: string | null; image: string | null; is_active?: boolean; sort_order?: number
}
