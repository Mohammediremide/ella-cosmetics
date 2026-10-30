from decimal import Decimal
from urllib.parse import parse_qs, unquote, urlparse

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Category, Product, StockMovement
from core.models import StoreSettings
from orders import services
from orders.models import Order
from orders.whatsapp import build_customer_url, normalize_wa_number

NUMBER = '2348088317529'


def user(email='a@example.com', staff=False):
    return User.objects.create_user(email=email, password='Str0ng-pass!x', name='Ada Obi', is_staff=staff)


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.cfg = StoreSettings.load()
        self.cfg.bank_name, self.cfg.account_name, self.cfg.account_number = 'Test Bank', 'Ella', '0123456789'
        self.cfg.save()
        self.alice, self.bob, self.admin = user('alice@example.com'), user('bob@example.com'), user('admin@example.com', True)
        self.p = Product.objects.create(name='Lip Tint', price=Decimal('12500'), stock_quantity=10, category=Category.objects.get(name='Makeup'))
        self.ac, self.bc, self.adm = APIClient(), APIClient(), APIClient()
        self.ac.force_login(self.alice); self.bc.force_login(self.bob); self.adm.force_login(self.admin)
        self.order, _ = services.create_order(user=self.alice, items=[(self.p.id, 2)], customer_name='Ada Obi', customer_phone='08031234567', delivery_method='pickup')

    def stock(self):
        self.p.refresh_from_db(); return self.p.stock_quantity

    def submit(self, client=None, ref=None):
        return (client or self.ac).post(f'/api/orders/{ref or self.order.reference}/submit-payment/')


class WhatsAppTests(Base):
    def test_default_number_is_the_business_number(self):
        self.assertEqual(StoreSettings.objects.get(pk=1).whatsapp_number, NUMBER)

    def test_normalisation_variants(self):
        for raw in ('+234 808 831 7529', '2348088317529', '08088317529', '+234 (0)808 831 7529', '0808 831 7529', '234-0808-831-7529'):
            self.assertEqual(normalize_wa_number(raw), NUMBER, raw)

    def test_receipt_link_has_number_order_and_amount(self):
        d = self.ac.get(f'/api/orders/{self.order.reference}/').json()
        u = urlparse(d['whatsapp_url'])
        self.assertEqual((u.scheme, u.netloc, u.path), ('https', 'wa.me', f'/{NUMBER}'))
        text = parse_qs(u.query)['text'][0]
        self.assertEqual(text, f'Hello Ella Cosmetics, I have made a bank transfer for order {self.order.reference} totaling ₦25,000. '
                               'I have attached my payment receipt. Please verify my payment. Thank you.')
        self.assertNotIn('+', u.path); self.assertNotIn(' ', d['whatsapp_url'])

    def test_every_link_uses_the_one_configured_number(self):
        d = self.ac.get(f'/api/orders/{self.order.reference}/').json()
        self.assertIn(f'wa.me/{NUMBER}?', d['whatsapp_url']); self.assertIn(f'wa.me/{NUMBER}?', d['whatsapp_support_url'])
        self.assertEqual(APIClient().get('/api/settings/').json()['whatsapp_number'], NUMBER)
        self.adm.patch('/api/admin/settings/', {'whatsapp_number': '+234 801 111 2222'}, format='json')
        d = self.ac.get(f'/api/orders/{self.order.reference}/').json()
        self.assertIn('wa.me/2348011112222?', d['whatsapp_url']); self.assertIn('wa.me/2348011112222?', d['whatsapp_support_url'])
        self.assertEqual(APIClient().get('/api/settings/').json()['whatsapp_number'], '2348011112222')

    def test_admin_can_save_local_format_and_it_is_normalised(self):
        r = self.adm.patch('/api/admin/settings/', {'whatsapp_number': '08088317529'}, format='json')
        self.assertEqual(r.json()['whatsapp_number'], NUMBER)

    def test_migration_does_not_overwrite_a_saved_number(self):
        from importlib import import_module
        from django.apps import apps
        m = import_module('core.migrations.0004_default_whatsapp_number')
        self.cfg.whatsapp_number = '2348011112222'; self.cfg.save()
        m.fill_blank_only(apps, None)
        self.assertEqual(StoreSettings.objects.get(pk=1).whatsapp_number, '2348011112222')
        self.cfg.whatsapp_number = ''; self.cfg.save()
        m.fill_blank_only(apps, None)
        self.assertEqual(StoreSettings.objects.get(pk=1).whatsapp_number, NUMBER)

    def test_admin_customer_link_converts_local_phone(self):
        self.assertTrue(build_customer_url(self.order, self.cfg).startswith('https://wa.me/2348031234567?text='))
        d = self.adm.get(f'/api/admin/orders/{self.order.pk}/').json()
        self.assertIn('wa.me/2348031234567', d['customer_whatsapp_url'])

    def test_no_link_when_number_cleared(self):
        self.adm.patch('/api/admin/settings/', {'whatsapp_number': ''}, format='json')
        self.assertEqual(self.ac.get(f'/api/orders/{self.order.reference}/').json()['whatsapp_url'], '')


class CustomerSubmitTests(Base):
    def test_new_order_awaits_payment(self):
        d = self.ac.get(f'/api/orders/{self.order.reference}/').json()
        self.assertEqual((d['payment_status'], d['payment_status_display']), ('awaiting_payment', 'Awaiting Payment'))
        self.assertIsNone(d['payment_submitted_at'])

    def test_done_moves_to_awaiting_verification_never_to_paid(self):
        r = self.submit()
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual((d['payment_status'], d['payment_status_display']), ('pending_verification', 'Processing — Awaiting Verification'))
        self.assertIsNotNone(d['payment_submitted_at'])
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.payment_status, 'verified')
        self.assertIsNone(self.order.payment_reviewed_at)
        self.assertEqual(self.order.fulfilment_status, 'pending')  # nothing ships before an admin verifies

    def test_status_persists_after_reload_and_new_login(self):
        self.submit()
        fresh = APIClient(); fresh.post('/api/auth/login/', {'email': 'alice@example.com', 'password': 'Str0ng-pass!x'}, format='json')
        self.assertEqual(fresh.get(f'/api/orders/{self.order.reference}/').json()['payment_status'], 'pending_verification')
        self.assertEqual(fresh.get('/api/orders/').json()['results'][0]['payment_status'], 'pending_verification')

    def test_repeated_presses_are_idempotent(self):
        first = self.submit().json()
        for _ in range(4):
            self.assertEqual(self.submit().status_code, 200)
        again = self.ac.get(f'/api/orders/{self.order.reference}/').json()
        self.assertEqual(again['payment_submitted_at'], first['payment_submitted_at'])  # timestamp not rewritten
        self.assertEqual(self.order.audit.filter(new_value='pending_verification').count(), 1)  # one record only
        self.assertEqual(Order.objects.count(), 1)

    def test_pressing_done_never_touches_stock(self):
        before = self.stock(); movements = StockMovement.objects.count()
        for _ in range(3): self.submit()
        self.assertEqual((self.stock(), StockMovement.objects.count()), (before, movements))

    def test_other_customer_cannot_submit_or_see_it(self):
        self.assertEqual(self.submit(self.bc).status_code, 404)
        self.order.refresh_from_db(); self.assertEqual(self.order.payment_status, 'awaiting_payment')
        self.assertEqual(self.submit(APIClient()).status_code, 403)

    def test_cannot_submit_cancelled_or_already_verified(self):
        services.set_payment_status(self.order.pk, 'verified', by=self.admin)
        r = self.submit(); self.assertEqual(r.status_code, 400); self.assertIn('already been verified', str(r.json()))
        o2, _ = services.create_order(user=self.alice, items=[(self.p.id, 1)], customer_name='A', customer_phone='08031234567', delivery_method='pickup')
        services.cancel_order(o2.pk, by=self.admin)
        r = self.submit(ref=o2.reference); self.assertEqual(r.status_code, 400)

    def test_customer_cannot_set_status_through_any_other_route(self):
        for body in ({'payment_status': 'verified'}, {'status': 'verified'}):
            self.assertEqual(self.ac.post(f'/api/admin/orders/{self.order.pk}/payment/', body, format='json').status_code, 403)
            self.assertEqual(self.ac.patch(f'/api/orders/{self.order.reference}/', body, format='json').status_code, 405)
        self.order.refresh_from_db(); self.assertEqual(self.order.payment_status, 'awaiting_payment')

    def test_submit_cannot_be_used_for_a_one_click_verify_via_extra_fields(self):
        self.ac.post(f'/api/orders/{self.order.reference}/submit-payment/', {'payment_status': 'verified', 'status': 'verified'}, format='json')
        self.order.refresh_from_db(); self.assertEqual(self.order.payment_status, 'pending_verification')

    def test_unpaid_orders_expire_but_submitted_ones_wait_for_an_admin(self):
        from datetime import timedelta
        from django.utils import timezone
        self.submit()
        Order.objects.filter(pk=self.order.pk).update(expires_at=timezone.now() - timedelta(hours=1))
        self.assertEqual(services.expire_unpaid_orders(), 0)  # customer claims they paid: never auto-cancelled
        self.order.refresh_from_db(); self.assertEqual(self.order.fulfilment_status, 'pending')


class AdminReviewTests(Base):
    def pay(self, status, **extra):
        return self.adm.post(f'/api/admin/orders/{self.order.pk}/payment/', {'status': status, **extra}, format='json')

    def test_verify_records_who_and_when_and_updates_customer(self):
        self.submit()
        r = self.pay('verified'); self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual((d['payment_status'], d['payment_reviewed_by']), ('verified', 'admin@example.com'))
        self.assertIsNotNone(d['payment_reviewed_at'])
        self.assertIn(('payment', 'pending_verification', 'verified', 'admin@example.com'), [(a['field'], a['from'], a['to'], a['by']) for a in d['audit']])
        mine = self.ac.get(f'/api/orders/{self.order.reference}/').json()
        self.assertEqual(mine['payment_status_display'], 'Payment Successful')
        self.assertIsNone(mine['bank'])  # no more transfer details once paid
        self.assertEqual(mine['fulfilment_status'], 'pending')  # paid != delivered
        self.assertNotIn('payment_reviewed_by', mine)  # staff identity is not shown to customers

    def test_reject_requires_a_reason_and_customer_sees_it(self):
        self.submit()
        for bad in ({}, {'reason': ''}, {'reason': '   '}):
            r = self.pay('rejected', **bad)
            self.assertEqual(r.status_code, 400); self.assertIn('reason', r.json()['error']['fields'])
        self.order.refresh_from_db(); self.assertEqual(self.order.payment_status, 'pending_verification')
        r = self.pay('rejected', reason='Amount received was ₦20,000, not ₦25,000')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['payment_reviewed_by'], 'admin@example.com')
        mine = self.ac.get(f'/api/orders/{self.order.reference}/').json()
        self.assertEqual((mine['payment_status_display'], mine['payment_rejection_reason']), ('Payment Rejected', 'Amount received was ₦20,000, not ₦25,000'))
        self.assertIn('wa.me/', mine['whatsapp_support_url'])
        self.assertIsNotNone(mine['bank'])  # they can still pay
        self.assertEqual(self.order.audit.filter(new_value='rejected').first().note, 'Amount received was ₦20,000, not ₦25,000')

    def test_rejected_customer_can_resubmit_and_old_rejection_is_cleared(self):
        self.submit(); self.pay('rejected', reason='Not received')
        self.assertEqual(self.submit().json()['payment_status'], 'pending_verification')
        self.order.refresh_from_db(); self.assertEqual(self.order.payment_rejection_reason, '')
        self.assertEqual(self.order.audit.filter(new_value='pending_verification').count(), 2)

    def test_admin_can_verify_without_the_done_button(self):
        self.assertEqual(self.pay('verified').json()['payment_status'], 'verified')  # customer paid and told them on WhatsApp only

    def test_only_staff_can_review(self):
        for client in (self.ac, self.bc, APIClient()):
            for body in ({'status': 'verified'}, {'status': 'rejected', 'reason': 'x'}):
                self.assertEqual(client.post(f'/api/admin/orders/{self.order.pk}/payment/', body, format='json').status_code, 403)
        self.order.refresh_from_db(); self.assertEqual(self.order.payment_status, 'awaiting_payment')

    def test_verification_and_rejection_never_change_stock(self):
        before = self.stock(); movements = StockMovement.objects.count()
        self.submit(); self.pay('rejected', reason='no'); self.submit(); self.pay('verified'); self.pay('verified')
        self.assertEqual((self.stock(), StockMovement.objects.count()), (before, movements))

    def test_rejection_then_expiry_restores_stock_exactly_once(self):
        from datetime import timedelta
        from django.utils import timezone
        self.submit(); self.pay('rejected', reason='No payment')
        Order.objects.filter(pk=self.order.pk).update(expires_at=timezone.now() - timedelta(hours=1))
        self.assertEqual([services.expire_unpaid_orders() for _ in range(3)], [1, 0, 0])
        self.assertEqual(self.stock(), 10)

    def test_verified_order_is_not_expired_and_cancel_restores_once(self):
        from datetime import timedelta
        from django.utils import timezone
        self.pay('verified')
        Order.objects.filter(pk=self.order.pk).update(expires_at=timezone.now() - timedelta(hours=1))
        self.assertEqual(services.expire_unpaid_orders(), 0)
        self.assertEqual(self.stock(), 8)
        for _ in range(2): services.cancel_order(self.order.pk, by=self.admin)
        self.assertEqual(self.stock(), 10)

    def test_invalid_transitions(self):
        from rest_framework.exceptions import ValidationError
        services.set_payment_status(self.order.pk, 'verified', by=self.admin)
        services.set_fulfilment_status(self.order.pk, 'processing', by=self.admin)
        with self.assertRaises(ValidationError):
            services.set_payment_status(self.order.pk, 'rejected', by=self.admin, reason='x')  # money already accepted & order in progress
        with self.assertRaises(ValidationError):
            services.submit_payment(self.order.pk, by=self.alice)

    def test_cancelled_unpaid_order_reads_cancelled_for_customer(self):
        services.cancel_order(self.order.pk, by=self.admin)
        d = self.ac.get(f'/api/orders/{self.order.reference}/').json()
        self.assertEqual((d['payment_status_display'], d['payment_tone']), ('Cancelled', 'cancelled'))
        self.assertIsNone(d['bank'])

    def test_payment_verification_queue_orders_by_submission_time(self):
        o2, _ = services.create_order(user=self.bob, items=[(self.p.id, 1)], customer_name='Bob', customer_phone='08099999999', delivery_method='pickup')
        self.submit(self.bc, o2.reference); self.submit()  # bob submits first, then alice
        rows = self.adm.get('/api/admin/orders/?payment_status=pending_verification&ordering=payment_submitted_at').json()['results']
        self.assertEqual([r['reference'] for r in rows], [o2.reference, self.order.reference])
        self.assertTrue(all(r['payment_submitted_at'] and r['customer_whatsapp_url'] for r in rows))
        self.assertEqual(self.adm.get('/api/admin/orders/?payment_status=awaiting_payment').json()['count'], 0)

    def test_overview_counts(self):
        self.submit()
        d = self.adm.get('/api/admin/overview/').json()
        self.assertEqual((d['awaiting_verification'], d['awaiting_payment'], d['verified_sales_total']), (1, 0, 0))
        self.pay('verified')
        d = self.adm.get('/api/admin/overview/').json()
        self.assertEqual((d['awaiting_verification'], Decimal(str(d['verified_sales_total']))), (0, Decimal('25000.00')))
