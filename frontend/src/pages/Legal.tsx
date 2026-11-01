import { Link } from 'react-router-dom'
import { usePublicSettings } from '../components/Layout'

// Editable starter pages. Business facts come from Admin → Settings; nothing is invented here.
// Not legal advice: the owner should have a qualified Nigerian lawyer review before launch.
const Todo = ({ children }: { children: React.ReactNode }) => <span className="rounded bg-amber-100 px-1.5 py-0.5 text-sm text-amber-900">[Owner to complete: {children}]</span>

export default function Legal({ kind }: { kind: 'privacy' | 'terms' }) {
  const { data: s } = usePublicSettings()
  const name = s?.store_name ?? 'Ella Cosmetics'
  const biz = s?.legal_business_name || null
  const contact = [s?.whatsapp_number && `WhatsApp +${s.whatsapp_number}`, s?.contact_email, s?.contact_phone].filter(Boolean).join(' · ')
  return (
    <div className="container-x max-w-2xl py-12">
      <h1 className="text-4xl">{kind === 'privacy' ? 'Privacy policy' : 'Terms of sale'}</h1>
      <p className="mt-3 rounded-brand bg-blush/50 p-3 text-xs leading-relaxed">This is a plain-language starter document and not legal advice. It does not guarantee compliance with any law. {name}’s owner should have it reviewed before launch. Highlighted items are details the owner still needs to provide.</p>
      <div className="mt-6 space-y-6 leading-relaxed text-ink/85 [&_h2]:mb-2 [&_h2]:text-2xl">
        <section><h2>Who we are</h2><p>This website is operated by {biz ?? name}{!biz && <> <Todo>registered business name, in Admin → Settings</Todo></>}. {s?.business_address ? `Address: ${s.business_address}.` : <Todo>business address, in Admin → Settings</Todo>} Contact: {contact || <Todo>contact details, in Admin → Settings</Todo>}.</p></section>
        {kind === 'privacy' ? (<>
          <section><h2>What we collect</h2><p>Your name, email address and password (stored only as a one-way hash) when you create an account; and your name, phone number, delivery address and order notes when you place an order. We also count visits to the site using an anonymous daily visitor code. We do not use advertising cookies and we don’t store your IP address for this.</p></section>
          <section><h2>How we use it</h2><p>To create your account, process and deliver your orders, check your bank transfer, contact you about your order (including by WhatsApp or phone), and keep the shop running safely. We don’t sell your information.</p></section>
          <section><h2>WhatsApp</h2><p>When you tap a WhatsApp button, your phone opens a chat with us. Anything you send there (including your payment receipt) is handled through WhatsApp and is subject to WhatsApp’s own privacy terms.</p></section>
          <section><h2>Payments</h2><p>We don’t process card payments and we don’t store card details. Payment is made by bank transfer into our account.</p></section>
          <section><h2>Your choices</h2><p>You can ask us to see, correct or delete the personal information we hold about you, subject to records we must keep (such as order records). Contact us using the details above. If you believe we’ve mishandled your data, you may also complain to the Nigeria Data Protection Commission.</p></section>
          <section><h2>Keeping it safe</h2><p>Order and account data is kept on secured servers. We keep order records for as long as needed for business and legal reasons <Todo>retention period</Todo>.</p></section>
        </>) : (<>
          <section><h2>Orders and prices</h2><p>Prices are shown in Nigerian naira (₦). When you place an order, we reserve the items for you. We check prices and stock when you order, so the total you see is the amount to pay.</p></section>
          <section><h2>Payment by bank transfer</h2><p>We currently accept manual bank transfer only. After ordering, transfer the exact total to the account shown, send your receipt to us on WhatsApp, and press “Done — I’ve Sent the Receipt”. That button only tells us to look for your payment. <strong>Your order is confirmed only after we see the money in our bank account</strong> and mark the payment as successful. If we can’t verify it, we’ll tell you why and how to fix it.</p></section>
          <section><h2>Unpaid orders</h2><p>If we have not received your payment within {s?.unpaid_order_hours ?? 24} hours of your order, the order may be cancelled automatically and the items released for other customers. Orders where you have told us you’ve paid are reviewed by our team first.</p></section>
          <section><h2>Delivery and pickup</h2><p>{s?.delivery_terms || <Todo>delivery areas, timelines and charges, in Admin → Settings</Todo>}</p></section>
          <section><h2>Cancellations, returns and refunds</h2><p>{s?.returns_terms || <Todo>your returns, exchange and refund policy, in Admin → Settings</Todo>} Nothing in these terms limits any rights you have under Nigerian consumer protection law.</p></section>
          <section><h2>Product information</h2><p>We try to describe and photograph products accurately, but colours may look different on different screens.</p></section>
        </>)}
        <p className="text-sm text-muted">See also our <Link className="text-burgundy underline" to={kind === 'privacy' ? '/terms' : '/privacy'}>{kind === 'privacy' ? 'Terms of sale' : 'Privacy policy'}</Link>.</p>
      </div>
    </div>
  )
}
