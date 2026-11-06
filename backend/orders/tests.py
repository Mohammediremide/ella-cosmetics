import io
import threading
from decimal import Decimal
from unittest import skipUnless

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, TransactionTestCase
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Category, Product
from core.models import StoreSettings
from orders import services
from orders.models import Order
from orders.whatsapp import build_whatsapp_url


def make_user(email='a@example.com', staff=False):
    return User.objects.create_user(email=email, password='Str0ng-pass!x', name='Test', is_staff=staff)


def make_product(name='Lipstick', price='12500.00', stock=5, **kw):
    return Product.objects.create(name=name, price=Decimal(price), stock_quantity=stock, **kw)


def checkout_payload(items, **kw):
    return {'customer_name': 'Ada', 'customer_phone': '08012345678', 'delivery_method': 'pickup', 'items': items, **kw}


class AuthTests(TestCase):
    def test_register_login_logout_and_no_hash_leak(self):
        c = APIClient()
        r = c.post('/api/auth/register/', {'name': 'Ada', 'email': 'ADA@Example.com', 'password': 'Str0ng-pass!x'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertNotIn('password', r.json())
        self.assertEqual(c.get('/api/auth/me/').json()['email'], 'ada@example.com')
        self.assertEqual(c.post('/api/auth/logout/').status_code, 204)
        self.assertFalse(c.get('/api/auth/me/').json().get('authenticated', True))

    def test_duplicate_email_and_weak_password(self):
        make_user('dup@example.com')
        c = APIClient()
        r = c.post('/api/auth/register/', {'name': 'X', 'email': 'dup@example.com', 'password': 'Str0ng-pass!x'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = c.post('/api/auth/register/', {'name': 'X', 'email': 'new@example.com', 'password': '123'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_cannot_self_register_as_staff(self):
        c = APIClient()
        c.post('/api/auth/register/', {'name': 'X', 'email': 'x@example.com', 'password': 'Str0ng-pass!x', 'is_staff': True}, format='json')
        self.assertFalse(User.objects.get(email='x@example.com').is_staff)

    def test_csrf_enforced_on_login_and_register(self):
        c = APIClient(enforce_csrf_checks=True)
        self.assertEqual(c.post('/api/auth/register/', {'name': 'X', 'email': 'c@example.com', 'password': 'Str0ng-pass!x'}, format='json').status_code, 403)
        self.assertEqual(c.post('/api/auth/login/', {'email': 'c@example.com', 'password': 'x'}, format='json').status_code, 403)
        r = c.post('/api/auth/login/', {'email': 'c@example.com', 'password': 'x'}, format='json')
        self_json = r.json()  # must be JSON, never an HTML error page
        assert self_json['error']['code'] == 'csrf_failed'
        token = c.get('/api/auth/csrf/').json()['csrfToken']
        r = c.post('/api/auth/register/', {'name': 'X', 'email': 'c@example.com', 'password': 'Str0ng-pass!x'}, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, 201)

    def test_bad_login_generic_error(self):
        make_user()
        r = APIClient().post('/api/auth/login/', {'email': 'a@example.com', 'password': 'wrong'}, format='json')
        self.assertEqual(r.status_code, 400)


class CheckoutTests(TestCase):
    def setUp(self):
        cache.clear()  # reset rate-limit counters between tests
        self.user = make_user()
        self.c = APIClient()
        self.c.force_login(self.user)
        self.p = make_product(stock=5)
        cfg = StoreSettings.load()
        cfg.pickup_enabled, cfg.delivery_enabled, cfg.delivery_fee = True, True, Decimal('2000')
        cfg.whatsapp_number, cfg.bank_name, cfg.account_name, cfg.account_number = '2348000000000', 'Test Bank', 'Ella', '0123456789'
        cfg.save()

    def order(self, qty=2, key=None, **kw):
        h = {'HTTP_IDEMPOTENCY_KEY': key} if key else {}
        return self.c.post('/api/checkout/', checkout_payload([{'product_id': self.p.id, 'quantity': qty}], **kw), format='json', **h)

    def test_server_side_price_and_stock_deduction(self):
        # a tampered client "price" field is simply ignored
        r = self.c.post('/api/checkout/', checkout_payload([{'product_id': self.p.id, 'quantity': 2, 'unit_price': '1'}]), format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Decimal(r.json()['total']), Decimal('25000.00'))
        self.assertEqual(r.json()['bank']['account_number'], '0123456789')
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock_quantity, 3)

    def test_delivery_fee_comes_from_settings(self):
        r = self.order(1, delivery_method='delivery', delivery_address='12 Allen Ave, Ikeja')
        self.assertEqual(Decimal(r.json()['total']), Decimal('14500.00'))

    def test_delivery_requires_address(self):
        self.assertEqual(self.order(1, delivery_method='delivery').status_code, 400)

    def test_dispatch_fields_are_required_only_when_dispatch_is_requested(self):
        invalid = self.order(1, dispatch_requested=True)
        self.assertEqual(invalid.status_code, 400)
        self.assertTrue({'dispatch_address', 'dispatch_state', 'dispatch_city', 'dispatch_phone'} <= set(invalid.json()['error']['fields']))
        self.assertEqual(Order.objects.count(), 0)

        regular = self.order(1, dispatch_requested=False)
        self.assertEqual(regular.status_code, 201, regular.content)
        self.assertFalse(regular.json()['dispatch_requested'])
        self.assertEqual(regular.json()['dispatch_status'], '')

    def test_dispatch_details_are_saved_without_changing_order_total(self):
        response = self.order(
            2, dispatch_requested=True, dispatch_address='12 Allen Avenue', dispatch_state='Lagos',
            dispatch_city='Ikeja', dispatch_phone='+234 801 234 5678', dispatch_instructions='Call on arrival',
        )
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(data['dispatch_status'], 'awaiting_dispatch')
        self.assertEqual(
            (data['dispatch_address'], data['dispatch_state'], data['dispatch_city'], data['dispatch_phone'], data['dispatch_instructions']),
            ('12 Allen Avenue', 'Lagos', 'Ikeja', '+234 801 234 5678', 'Call on arrival'),
        )
        self.assertEqual(Decimal(data['total']), Decimal('25000.00'))
        self.assertEqual(Decimal(data['delivery_fee']), Decimal('0.00'))

    def test_insufficient_stock_rejected_and_nothing_changes(self):
        r = self.order(6)
        self.assertEqual(r.status_code, 400)
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock_quantity, 5)
        self.assertEqual(Order.objects.count(), 0)

    def test_sequential_orders_cannot_oversell(self):
        self.assertEqual(self.order(3).status_code, 201)
        self.assertEqual(self.order(3).status_code, 400)

    def test_inactive_product_cannot_be_ordered(self):
        self.p.is_active = False
        self.p.save()
        self.assertEqual(self.order(1).status_code, 400)

    def test_duplicate_submission_same_key_creates_one_order(self):
        a, b = self.order(1, key='abc'), self.order(1, key='abc')
        self.assertEqual((a.status_code, b.status_code), (201, 200))
        self.assertEqual(a.json()['reference'], b.json()['reference'])
        self.assertEqual(Order.objects.count(), 1)
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock_quantity, 4)

    def test_snapshot_survives_product_edit(self):
        ref = self.order(1).json()['reference']
        self.p.price, self.p.name = Decimal('99999'), 'Renamed'
        self.p.save()
        item = self.c.get(f'/api/orders/{ref}/').json()['items'][0]
        self.assertEqual((item['product_name'], Decimal(item['unit_price'])), ('Lipstick', Decimal('12500.00')))

    def test_whatsapp_message_uses_saved_order(self):
        order = Order.objects.get(reference=self.order(2).json()['reference'])
        url = build_whatsapp_url(order, StoreSettings.load())
        self.assertTrue(url.startswith('https://wa.me/2348000000000?text='))
        self.assertIn(order.reference, url)
        self.assertIn('%E2%82%A625%2C000', url)  # ₦25,000, URL-encoded
        self.assertIn('totaling', __import__('urllib.parse').parse.unquote(url))

    def test_whatsapp_url_empty_without_number(self):
        cfg = StoreSettings.load(); cfg.whatsapp_number = ''; cfg.save()
        order = Order.objects.get(reference=self.order(1).json()['reference'])
        self.assertEqual(build_whatsapp_url(order, cfg), '')

    def test_checkout_requires_login(self):
        self.assertIn(APIClient().post('/api/checkout/', checkout_payload([]), format='json').status_code, (401, 403))


class OrderIsolationAndAdminTests(TestCase):
    def setUp(self):
        self.alice, self.bob, self.admin = make_user('alice@example.com'), make_user('bob@example.com'), make_user('admin@example.com', staff=True)
        self.p = make_product(stock=10)
        StoreSettings.load()
        self.order, _ = services.create_order(user=self.alice, items=[(self.p.id, 2)], customer_name='A', customer_phone='08011111111', delivery_method='pickup')
        self.alice_c, self.bob_c, self.admin_c = APIClient(), APIClient(), APIClient()
        self.alice_c.force_login(self.alice); self.bob_c.force_login(self.bob); self.admin_c.force_login(self.admin)

    def test_customer_cannot_read_others_order(self):
        self.assertEqual(self.bob_c.get(f'/api/orders/{self.order.reference}/').status_code, 404)
        self.assertEqual(self.bob_c.get('/api/orders/').json()['count'], 0)
        self.assertEqual(self.alice_c.get('/api/orders/').json()['count'], 1)

    def test_customer_cannot_use_admin_endpoints(self):
        for method, url in [('get', '/api/admin/orders/'), ('get', '/api/admin/overview/'), ('get', '/api/admin/settings/'),
                            ('post', '/api/admin/products/'), ('get', '/api/admin/products/')]:
            self.assertEqual(getattr(self.alice_c, method)(url).status_code, 403, url)
        self.assertEqual(APIClient().get('/api/admin/orders/').status_code, 403)

    def test_customer_cannot_verify_payment_or_change_settings(self):
        self.assertEqual(self.alice_c.post(f'/api/admin/orders/{self.order.pk}/payment/', {'status': 'verified'}, format='json').status_code, 403)
        self.assertEqual(self.alice_c.patch('/api/admin/settings/', {'bank_name': 'Evil'}, format='json').status_code, 403)

    def test_dispatch_is_private_and_admin_updates_status_independently(self):
        dispatch_order, _ = services.create_order(
            user=self.alice, items=[(self.p.id, 1)], customer_name='A', customer_phone='08011111111',
            delivery_method='pickup', dispatch_requested=True, dispatch_address='1 Main Street',
            dispatch_state='Lagos', dispatch_city='Ikeja', dispatch_phone='08022222222',
        )
        customer_data = self.alice_c.get(f'/api/orders/{dispatch_order.reference}/').json()
        self.assertEqual((customer_data['dispatch_requested'], customer_data['dispatch_status']), (True, 'awaiting_dispatch'))
        self.assertEqual(self.bob_c.get(f'/api/orders/{dispatch_order.reference}/').status_code, 404)
        self.assertEqual(self.alice_c.post(
            f'/api/admin/orders/{dispatch_order.pk}/dispatch/', {'status': 'dispatched'}, format='json',
        ).status_code, 403)

        response = self.admin_c.post(
            f'/api/admin/orders/{dispatch_order.pk}/dispatch/', {'status': 'dispatched'}, format='json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        dispatch_order.refresh_from_db()
        self.assertEqual(dispatch_order.dispatch_status, 'dispatched')
        self.assertEqual(dispatch_order.payment_status, Order.Payment.AWAITING)
        self.assertEqual(dispatch_order.fulfilment_status, Order.Fulfilment.PENDING)
        self.assertEqual(response.json()['audit'][0]['field'], 'dispatch_status')
        self.assertEqual(self.alice_c.get(f'/api/orders/{dispatch_order.reference}/').json()['dispatch_status'], 'dispatched')
        self.assertEqual(self.admin_c.post(
            f'/api/admin/orders/{self.order.pk}/dispatch/', {'status': 'delivered'}, format='json',
        ).status_code, 400)

    def test_dispatch_order_counts_and_existing_overview_include_both_categories(self):
        dispatch_order, _ = services.create_order(
            user=self.bob, items=[(self.p.id, 1)], customer_name='B', customer_phone='08033333333',
            delivery_method='pickup', dispatch_requested=True, dispatch_address='2 Main Street',
            dispatch_state='Lagos', dispatch_city='Yaba', dispatch_phone='08044444444',
        )
        pending_dispatch_order, _ = services.create_order(
            user=self.bob, items=[(self.p.id, 1)], customer_name='B', customer_phone='08033333333',
            delivery_method='pickup', dispatch_requested=True, dispatch_address='3 Main Street',
            dispatch_state='Lagos', dispatch_city='Surulere', dispatch_phone='08055555555',
        )
        services.set_payment_status(self.order.pk, Order.Payment.VERIFIED, by=self.admin)
        services.set_payment_status(dispatch_order.pk, Order.Payment.VERIFIED, by=self.admin)
        services.submit_payment(pending_dispatch_order.pk, by=self.bob)

        overview = self.admin_c.get('/api/admin/overview/').json()
        self.assertEqual((overview['total_orders'], overview['orders_with_dispatch'], overview['orders_without_dispatch']), (3, 2, 1))
        self.assertEqual((overview['awaiting_verification'], overview['awaiting_payment']), (1, 0))
        self.assertEqual(Decimal(str(overview['verified_sales_total'])), Decimal('37500.00'))
        with_dispatch = self.admin_c.get('/api/admin/orders/?dispatch_requested=true').json()
        without_dispatch = self.admin_c.get('/api/admin/orders/?dispatch_requested=false').json()
        self.assertEqual((with_dispatch['count'], without_dispatch['count']), (2, 1))
        self.assertEqual({row['reference'] for row in with_dispatch['results']}, {dispatch_order.reference, pending_dispatch_order.reference})
        self.assertEqual(without_dispatch['results'][0]['reference'], self.order.reference)

    def test_public_settings_hide_bank_details(self):
        cfg = StoreSettings.load(); cfg.account_number = '0123456789'; cfg.save()
        self.assertNotIn('account_number', APIClient().get('/api/settings/').json())

    def test_admin_verifies_payment_with_audit_then_processes(self):
        r = self.admin_c.post(f'/api/admin/orders/{self.order.pk}/payment/', {'status': 'verified'}, format='json')
        self.assertEqual(r.json()['payment_status'], 'verified')
        self.assertEqual(r.json()['audit'][0]['by'], 'admin@example.com')
        r = self.admin_c.post(f'/api/admin/orders/{self.order.pk}/fulfilment/', {'status': 'processing'}, format='json')
        self.assertEqual(r.json()['fulfilment_status'], 'processing')

    def test_cannot_process_before_payment_verified(self):
        r = self.admin_c.post(f'/api/admin/orders/{self.order.pk}/fulfilment/', {'status': 'processing'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_cancel_restores_stock_once(self):
        self.p.refresh_from_db(); self.assertEqual(self.p.stock_quantity, 8)
        for _ in range(2):  # second call must not restore again
            self.admin_c.post(f'/api/admin/orders/{self.order.pk}/fulfilment/', {'status': 'cancelled'}, format='json')
        self.p.refresh_from_db(); self.assertEqual(self.p.stock_quantity, 10)

    def test_admin_can_delete_unpaid_order_and_restore_stock(self):
        self.p.refresh_from_db(); self.assertEqual(self.p.stock_quantity, 8)
        response = self.admin_c.delete(f'/api/admin/orders/{self.order.pk}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Order.objects.filter(pk=self.order.pk).exists())
        self.p.refresh_from_db(); self.assertEqual(self.p.stock_quantity, 10)
        movement = self.p.movements.get(kind='released')
        self.assertEqual((movement.delta, movement.order, movement.reason), (2, None, f'Deleted order {self.order.reference}'))

    def test_order_delete_is_staff_only_and_protects_paid_orders(self):
        url = f'/api/admin/orders/{self.order.pk}/'
        self.assertEqual(self.alice_c.delete(url).status_code, 403)
        services.set_payment_status(self.order.pk, 'verified', by=self.admin)
        response = self.admin_c.delete(url)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())

    def test_expired_orders_release_stock(self):
        from datetime import timedelta
        from django.utils import timezone
        Order.objects.filter(pk=self.order.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(services.expire_unpaid_orders(), 1)
        self.p.refresh_from_db(); self.assertEqual(self.p.stock_quantity, 10)

    def test_overview_counts_only_verified_as_sales(self):
        self.assertEqual(self.admin_c.get('/api/admin/overview/').json()['verified_sales_total'], 0)
        services.set_payment_status(self.order.pk, 'verified', by=self.admin)
        self.assertEqual(Decimal(str(self.admin_c.get('/api/admin/overview/').json()['verified_sales_total'])), Decimal('25000.00'))


class CatalogAdminTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@example.com', staff=True)
        self.c = APIClient(); self.c.force_login(self.admin)

    def png(self, name='a.png', fmt='PNG'):
        buf = io.BytesIO(); Image.new('RGB', (10, 10)).save(buf, fmt); return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')

    def test_create_edit_and_stock_status(self):
        cat = Category.objects.create(name='Lips')
        r = self.c.post('/api/admin/products/', {'name': 'Gloss', 'price': '4500', 'stock_quantity': 3, 'category_id': cat.id, 'description': 'x'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['stock_status'], 'low_stock')  # 3 <= default threshold 5
        pid = r.json()['id']
        r = self.c.patch(f'/api/admin/products/{pid}/', {'stock_quantity': 0, 'price': '5000'}, format='json')
        self.assertEqual(r.json()['stock_status'], 'out_of_stock')
        self.assertEqual(len(self.c.get(f'/api/admin/products/{pid}/stock-history/').json()), 2)

    def test_negative_stock_and_price_rejected(self):
        self.assertEqual(self.c.post('/api/admin/products/', {'name': 'X', 'price': '10', 'stock_quantity': -1}, format='json').status_code, 400)
        self.assertEqual(self.c.post('/api/admin/products/', {'name': 'X', 'price': '-10', 'stock_quantity': 1}, format='json').status_code, 400)

    def test_adjust_stock_cannot_go_negative(self):
        p = make_product(stock=2)
        self.assertEqual(self.c.post(f'/api/admin/products/{p.id}/adjust-stock/', {'delta': -3, 'reason': 'x'}, format='json').status_code, 400)
        self.assertEqual(self.c.post(f'/api/admin/products/{p.id}/adjust-stock/', {'delta': 4, 'reason': 'restock'}, format='json').json()['stock_quantity'], 6)

    def test_image_upload_validation(self):
        p = make_product()
        ok = self.c.post(f'/api/admin/products/{p.id}/images/', {'image': self.png()}, format='multipart')
        self.assertEqual(ok.status_code, 201, ok.content)
        fake = SimpleUploadedFile('evil.png', b'<?php echo 1; ?>', content_type='image/png')
        self.assertEqual(self.c.post(f'/api/admin/products/{p.id}/images/', {'image': fake}, format='multipart').status_code, 400)

    def test_inactive_products_hidden_from_storefront_and_delete_archives(self):
        p = make_product()
        self.assertEqual(APIClient().get('/api/products/').json()['count'], 1)
        self.c.delete(f'/api/admin/products/{p.id}/')
        self.assertEqual(APIClient().get('/api/products/').json()['count'], 0)
        self.assertEqual(APIClient().get(f'/api/products/{p.slug}/').status_code, 404)

    def test_new_badge_from_real_dates(self):
        from datetime import timedelta
        from django.utils import timezone
        old = make_product('Old'); Product.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=90))
        make_product('Fresh')
        flags = {p['name']: p['is_new'] for p in APIClient().get('/api/products/').json()['results']}
        self.assertEqual(flags, {'Old': False, 'Fresh': True})

    def test_settings_validation(self):
        r = self.c.patch('/api/admin/settings/', {'account_number': '123'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.c.patch('/api/admin/settings/', {'account_number': '0123456789', 'whatsapp_number': '+234 801 234 5678'}, format='json')
        self.assertEqual(r.json()['whatsapp_number'], '2348012345678')


class CartTests(TestCase):
    def test_guest_validate_clamps_to_stock_and_uses_db_price(self):
        p = make_product(stock=2)
        r = APIClient().post('/api/cart/validate/', {'items': [{'product_id': p.id, 'quantity': 9}]}, format='json').json()
        self.assertEqual((r['items'][0]['quantity'], r['adjusted']), (2, True))
        self.assertEqual(Decimal(str(r['subtotal'])), Decimal('25000.00'))

    def test_merge_guest_cart_into_account_cart(self):
        u, p = make_user(), make_product(stock=5)
        c = APIClient(); c.force_login(u)
        c.put('/api/cart/', {'items': [{'product_id': p.id, 'quantity': 2}]}, format='json')
        r = c.post('/api/cart/merge/', {'items': [{'product_id': p.id, 'quantity': 2}]}, format='json').json()
        self.assertEqual(r['items'][0]['quantity'], 4)
        r = c.post('/api/cart/merge/', {'items': [{'product_id': p.id, 'quantity': 5}]}, format='json').json()
        self.assertEqual(r['items'][0]['quantity'], 5)  # clamped to stock


@skipUnless(connection.vendor == 'postgresql', 'Row-level locking can only be verified on PostgreSQL (run with DATABASE_URL set)')
class ConcurrencyTests(TransactionTestCase):
    def test_concurrent_checkouts_never_oversell(self):
        p = make_product(stock=3)
        users = [make_user(f'u{i}@example.com') for i in range(8)]
        results = []

        def go(u):
            try:
                services.create_order(user=u, items=[(p.id, 1)], customer_name='x', customer_phone='08011111111', delivery_method='pickup')
                results.append('ok')
            except Exception:
                results.append('fail')
            finally:
                connection.close()

        StoreSettings.load()
        ts = [threading.Thread(target=go, args=(u,)) for u in users]
        [t.start() for t in ts]; [t.join() for t in ts]
        p.refresh_from_db()
        self.assertEqual(results.count('ok'), 3)
        self.assertEqual(p.stock_quantity, 0)


# ======================= Expiry, transitions, ownership, uploads =======================
from datetime import timedelta
from unittest import mock
from django.utils import timezone
from catalog.models import StockMovement


def expired_order(user, product, qty=2, **fields):
    o, _ = services.create_order(user=user, items=[(product.id, qty)], customer_name='A', customer_phone='08011111111', delivery_method='pickup')
    Order.objects.filter(pk=o.pk).update(expires_at=timezone.now() - timedelta(minutes=1), **fields)
    return Order.objects.get(pk=o.pk)


class ExpiryTests(TestCase):
    def setUp(self):
        cache.clear()
        StoreSettings.load()
        self.user, self.p = make_user(), make_product(stock=10)

    def stock(self):
        self.p.refresh_from_db(); return self.p.stock_quantity

    def test_expires_unpaid_order_and_restores_stock(self):
        o = expired_order(self.user, self.p)
        self.assertEqual(self.stock(), 8)
        self.assertEqual(services.expire_unpaid_orders(), 1)
        o.refresh_from_db()
        self.assertEqual((o.fulfilment_status, self.stock()), ('cancelled', 10))
        self.assertEqual(o.audit.first().by if False else o.audit.first().changed_by, None)  # system action

    def test_repeated_runs_restore_exactly_once(self):
        expired_order(self.user, self.p)
        self.assertEqual([services.expire_unpaid_orders() for _ in range(3)], [1, 0, 0])
        self.assertEqual(self.stock(), 10)
        self.assertEqual(StockMovement.objects.filter(kind='released').count(), 1)

    def test_already_cancelled_order_not_restored_again(self):
        o = expired_order(self.user, self.p)
        services.cancel_order(o.pk, by=None)
        self.assertEqual(services.expire_unpaid_orders(), 0)
        self.assertEqual(self.stock(), 10)

    def test_verified_order_never_expires(self):
        o = expired_order(self.user, self.p, payment_status='verified')
        self.assertEqual(services.expire_unpaid_orders(), 0)
        o.refresh_from_db()
        self.assertEqual((o.fulfilment_status, self.stock()), ('pending', 8))

    def test_unexpired_order_untouched(self):
        services.create_order(user=self.user, items=[(self.p.id, 1)], customer_name='A', customer_phone='08011111111', delivery_method='pickup')
        self.assertEqual(services.expire_unpaid_orders(), 0)
        self.assertEqual(self.stock(), 9)

    def test_rejected_unpaid_order_also_expires(self):
        expired_order(self.user, self.p, payment_status='rejected')
        self.assertEqual(services.expire_unpaid_orders(), 1)
        self.assertEqual(self.stock(), 10)

    def test_processing_order_not_expired(self):
        expired_order(self.user, self.p, payment_status='verified', fulfilment_status='processing')
        self.assertEqual(services.expire_unpaid_orders(), 0)

    def test_payment_verified_after_listing_wins_the_race(self):
        """Job lists the order as expired, admin verifies, job then tries to cancel => must not cancel."""
        o = expired_order(self.user, self.p)
        Order.objects.filter(pk=o.pk).update(payment_status='verified')
        services.cancel_order(o.pk, by=None, only_if_expired=timezone.now())
        o.refresh_from_db()
        self.assertEqual((o.fulfilment_status, self.stock()), ('pending', 8))

    def test_one_failure_does_not_block_other_orders(self):
        a = expired_order(self.user, self.p, 1)
        b = expired_order(make_user('b@example.com'), self.p, 1)
        real = services.cancel_order
        calls = []

        def flaky(oid, **kw):
            calls.append(oid)
            if len(calls) == 1:
                raise RuntimeError('boom')
            return real(oid, **kw)
        with mock.patch.object(services, 'cancel_order', flaky), self.assertLogs('orders.services', 'ERROR'):
            n = services.expire_unpaid_orders()
        self.assertEqual(n, 1)
        self.assertEqual(Order.objects.filter(fulfilment_status='cancelled').count(), 1)
        self.assertEqual(services.expire_unpaid_orders(), 1)  # next run picks up the one that failed
        self.assertEqual(self.stock(), 10)

    def test_management_command(self):
        from django.core.management import call_command
        from io import StringIO
        expired_order(self.user, self.p)
        out = StringIO(); call_command('expire_orders', stdout=out)
        self.assertIn('Expired 1 order', out.getvalue())

    def test_expiry_window_comes_from_settings(self):
        cfg = StoreSettings.load(); cfg.unpaid_order_hours = 2; cfg.save()
        o, _ = services.create_order(user=self.user, items=[(self.p.id, 1)], customer_name='A', customer_phone='08011111111', delivery_method='pickup')
        self.assertAlmostEqual((o.expires_at - timezone.now()).total_seconds(), 7200, delta=30)


class TransitionTests(TestCase):
    def setUp(self):
        cache.clear(); StoreSettings.load()
        self.user, self.admin, self.p = make_user(), make_user('admin@example.com', staff=True), make_product(stock=10)
        self.o, _ = services.create_order(user=self.user, items=[(self.p.id, 2)], customer_name='A', customer_phone='08011111111', delivery_method='pickup')

    def fail(self, fn, *a, **kw):
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            fn(*a, **kw)

    def test_full_happy_path_and_stock_untouched_by_verification(self):
        services.set_payment_status(self.o.pk, 'verified', by=self.admin)
        for s in ('processing', 'dispatched', 'delivered'):
            services.set_fulfilment_status(self.o.pk, s, by=self.admin)
        self.p.refresh_from_db(); self.assertEqual(self.p.stock_quantity, 8)  # deducted once at creation only
        self.assertEqual(StockMovement.objects.filter(product=self.p).count(), 1)

    def test_invalid_jumps_blocked(self):
        services.set_payment_status(self.o.pk, 'verified', by=self.admin)
        self.fail(services.set_fulfilment_status, self.o.pk, 'delivered', by=self.admin)
        self.fail(services.set_fulfilment_status, self.o.pk, 'dispatched', by=self.admin)

    def test_cannot_ship_unpaid(self):
        self.fail(services.set_fulfilment_status, self.o.pk, 'processing', by=self.admin)
        services.set_payment_status(self.o.pk, 'rejected', by=self.admin, reason='No transfer seen')
        self.fail(services.set_fulfilment_status, self.o.pk, 'processing', by=self.admin)

    def test_payment_can_be_reset_to_pending_before_processing_only(self):
        services.set_payment_status(self.o.pk, 'verified', by=self.admin)
        services.set_payment_status(self.o.pk, 'awaiting_payment', by=self.admin)
        services.set_payment_status(self.o.pk, 'verified', by=self.admin)
        services.set_fulfilment_status(self.o.pk, 'processing', by=self.admin)
        self.fail(services.set_payment_status, self.o.pk, 'rejected', by=self.admin, reason='x')

    def test_cannot_cancel_after_dispatch_and_cancelled_is_final(self):
        services.set_payment_status(self.o.pk, 'verified', by=self.admin)
        services.set_fulfilment_status(self.o.pk, 'processing', by=self.admin)
        services.set_fulfilment_status(self.o.pk, 'dispatched', by=self.admin)
        self.fail(services.cancel_order, self.o.pk, by=self.admin)
        o2, _ = services.create_order(user=self.user, items=[(self.p.id, 1)], customer_name='A', customer_phone='08011111111', delivery_method='pickup')
        services.cancel_order(o2.pk, by=self.admin)
        self.fail(services.set_payment_status, o2.pk, 'verified', by=self.admin)
        self.fail(services.set_fulfilment_status, o2.pk, 'processing', by=self.admin)

    def test_unknown_status_rejected(self):
        self.fail(services.set_payment_status, self.o.pk, 'paid-lol', by=self.admin)
        self.fail(services.set_fulfilment_status, self.o.pk, 'teleported', by=self.admin)

    def test_every_change_is_audited_with_actor(self):
        services.set_payment_status(self.o.pk, 'verified', by=self.admin)
        services.set_fulfilment_status(self.o.pk, 'processing', by=self.admin)
        rows = list(self.o.audit.values_list('field', 'new_value', 'changed_by__email'))
        self.assertIn(('payment', 'verified', 'admin@example.com'), rows)
        self.assertIn(('fulfilment', 'processing', 'admin@example.com'), rows)


class OwnershipTests(TestCase):
    def setUp(self):
        cache.clear(); StoreSettings.load()
        self.alice, self.bob = make_user('alice@example.com'), make_user('bob@example.com')
        self.p = make_product(stock=10)
        self.ac, self.bc = APIClient(), APIClient()
        self.ac.force_login(self.alice); self.bc.force_login(self.bob)

    def test_customer_cannot_modify_orders_or_protected_fields(self):
        o, _ = services.create_order(user=self.alice, items=[(self.p.id, 1)], customer_name='A', customer_phone='08011111111', delivery_method='pickup')
        url = f'/api/orders/{o.reference}/'
        for m in ('patch', 'put', 'delete', 'post'):
            self.assertEqual(getattr(self.ac, m)(url, {'payment_status': 'verified', 'total': '1'}, format='json').status_code, 405, m)
        o.refresh_from_db(); self.assertEqual((o.payment_status, o.total), ('awaiting_payment', Decimal('12500.00')))

    def test_carts_are_private_per_user(self):
        self.ac.put('/api/cart/', {'items': [{'product_id': self.p.id, 'quantity': 3}]}, format='json')
        self.assertEqual(self.bc.get('/api/cart/').json()['items'], [])
        self.assertEqual(self.ac.get('/api/cart/').json()['items'][0]['quantity'], 3)
        self.assertEqual(APIClient().get('/api/cart/').status_code, 403)

    def test_checkout_uses_own_cart_only(self):
        self.ac.put('/api/cart/', {'items': [{'product_id': self.p.id, 'quantity': 3}]}, format='json')
        r = self.bc.post('/api/checkout/', {'customer_name': 'B', 'customer_phone': '08011111111', 'delivery_method': 'pickup'}, format='json')
        self.assertEqual(r.status_code, 400)  # Bob's cart is empty; Alice's is untouched
        self.assertEqual(self.ac.get('/api/cart/').json()['items'][0]['quantity'], 3)

    def test_same_idempotency_key_is_per_user(self):
        a, _ = services.create_order(user=self.alice, items=[(self.p.id, 1)], customer_name='A', customer_phone='08011111111', delivery_method='pickup', idempotency_key='k')
        b, created = services.create_order(user=self.bob, items=[(self.p.id, 1)], customer_name='B', customer_phone='08011111111', delivery_method='pickup', idempotency_key='k')
        self.assertTrue(created); self.assertNotEqual(a.pk, b.pk)

    def test_bank_details_hidden_once_verified(self):
        o, _ = services.create_order(user=self.alice, items=[(self.p.id, 1)], customer_name='A', customer_phone='08011111111', delivery_method='pickup')
        self.assertIsNotNone(self.ac.get(f'/api/orders/{o.reference}/').json()['bank'])
        Order.objects.filter(pk=o.pk).update(payment_status='verified')
        self.assertIsNone(self.ac.get(f'/api/orders/{o.reference}/').json()['bank'])

    def test_negative_and_zero_quantities_rejected(self):
        for q in (0, -1, 100):
            r = self.ac.post('/api/checkout/', {'customer_name': 'A', 'customer_phone': '08011111111', 'delivery_method': 'pickup', 'items': [{'product_id': self.p.id, 'quantity': q}]}, format='json')
            self.assertEqual(r.status_code, 400, q)
        self.assertEqual(Order.objects.count(), 0)


class AdminCatalogExtraTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin, self.cust = make_user('admin@example.com', staff=True), make_user('c@example.com')
        self.c = APIClient(); self.c.force_login(self.admin)

    def img(self, fmt='PNG', name='a.png'):
        buf = io.BytesIO(); Image.new('RGB', (12, 12), (200, 100, 120)).save(buf, fmt); return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')

    def test_category_crud_and_permissions(self):
        r = self.c.post('/api/admin/categories/', {'name': 'Skin'}, format='json')
        self.assertEqual(r.status_code, 201); cid = r.json()['id']
        self.assertEqual(self.c.patch(f'/api/admin/categories/{cid}/', {'name': 'Skincare'}, format='json').json()['name'], 'Skincare')
        cust = APIClient(); cust.force_login(self.cust)
        self.assertEqual(cust.post('/api/admin/categories/', {'name': 'Hack'}, format='json').status_code, 403)
        self.assertEqual(cust.delete(f'/api/admin/categories/{cid}/').status_code, 403)
        p = make_product(category=Category.objects.get(pk=cid))
        self.assertEqual(self.c.delete(f'/api/admin/categories/{cid}/').status_code, 409)  # has products: must deactivate instead
        p.refresh_from_db(); self.assertEqual(p.category_id, cid)

    def test_category_image_validated(self):
        cid = self.c.post('/api/admin/categories/', {'name': 'Eyes'}, format='json').json()['id']
        bad = SimpleUploadedFile('x.png', b'not an image', content_type='image/png')
        self.assertEqual(self.c.patch(f'/api/admin/categories/{cid}/', {'image': bad}, format='multipart').status_code, 400)
        ok = self.c.patch(f'/api/admin/categories/{cid}/', {'image': self.img()}, format='multipart')
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertTrue(ok.json()['image'].startswith('/media/categories/'))  # relative URL

    def test_image_rejections(self):
        p = make_product()
        url = f'/api/admin/products/{p.id}/images/'
        gif = io.BytesIO(); Image.new('P', (5, 5)).save(gif, 'GIF')
        self.assertEqual(self.c.post(url, {'image': SimpleUploadedFile('a.gif', gif.getvalue(), content_type='image/gif')}, format='multipart').status_code, 400)
        full = io.BytesIO(); Image.new('RGB', (40, 40)).save(full, 'PNG')
        trunc = SimpleUploadedFile('t.png', full.getvalue()[:60], content_type='image/png')
        self.assertEqual(self.c.post(url, {'image': trunc}, format='multipart').status_code, 400)
        big = SimpleUploadedFile('big.png', b'0' * (5 * 1024 * 1024 + 1), content_type='image/png')
        self.assertEqual(self.c.post(url, {'image': big}, format='multipart').status_code, 400)
        self.assertEqual(self.c.post(url, {}, format='multipart').status_code, 400)
        self.assertEqual(p.images.count(), 0)

    def test_upload_replace_delete_and_public_url(self):
        p = make_product()
        r = self.c.post(f'/api/admin/products/{p.id}/images/', {'image': self.img(), 'alt_text': 'Rose lipstick'}, format='multipart')
        self.assertEqual(r.status_code, 201); iid, first = r.json()['id'], r.json()['image']
        pub = APIClient().get(f'/api/products/{p.slug}/').json()
        self.assertEqual(pub['images'][0]['image'], first)
        rep = self.c.patch(f'/api/admin/product-images/{iid}/', {'image': self.img('JPEG', 'b.jpg')}, format='multipart')
        self.assertEqual(rep.status_code, 200, rep.content); self.assertNotEqual(rep.json()['image'], first)
        self.assertEqual(self.c.delete(f'/api/admin/product-images/{iid}/').status_code, 204)
        self.assertEqual(p.images.count(), 0)

    def test_customer_cannot_upload_or_edit_images(self):
        p = make_product(); cust = APIClient(); cust.force_login(self.cust)
        self.assertEqual(cust.post(f'/api/admin/products/{p.id}/images/', {'image': self.img()}, format='multipart').status_code, 403)

    def test_settings_persist_and_public_endpoint_has_legal_but_no_bank(self):
        r = self.c.patch('/api/admin/settings/', {'bank_name': 'GTBank', 'account_name': 'Ella', 'account_number': '0123456789', 'whatsapp_number': '2348012345678',
                                                  'legal_business_name': 'Ella Beauty', 'returns_terms': 'Contact us within 7 days.', 'unpaid_order_hours': 12}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        again = self.c.get('/api/admin/settings/').json()
        self.assertEqual((again['bank_name'], again['unpaid_order_hours']), ('GTBank', 12))
        pub = APIClient().get('/api/settings/').json()
        self.assertEqual(pub['legal_business_name'], 'Ella Beauty')
        for k in ('bank_name', 'account_name', 'account_number'):
            self.assertNotIn(k, pub)
        self.assertEqual(self.c.patch('/api/admin/settings/', {'unpaid_order_hours': 0}, format='json').status_code, 400)

    def test_stock_history_records_every_change(self):
        p = make_product(stock=5)
        self.c.post(f'/api/admin/products/{p.id}/adjust-stock/', {'delta': 3, 'reason': 'restock'}, format='json')
        self.c.patch(f'/api/admin/products/{p.id}/', {'stock_quantity': 1}, format='json')
        h = self.c.get(f'/api/admin/products/{p.id}/stock-history/').json()
        self.assertEqual([x['delta'] for x in h], [-7, 3])
        self.assertEqual(h[0]['by'], 'admin@example.com')

    def test_admin_lists_are_paginated(self):
        for i in range(15): make_product(f'P{i}')
        r = self.c.get('/api/admin/products/').json()
        self.assertEqual((r['count'], len(r['results'])), (15, 12))
        self.assertEqual(len(self.c.get('/api/admin/products/?page=2').json()['results']), 3)


@skipUnless(connection.vendor == 'postgresql', 'Needs PostgreSQL row locking')
class PostgresConcurrencyTests(TransactionTestCase):
    def setUp(self):
        cache.clear(); StoreSettings.load()

    def _run(self, fns):
        out, ts = [], []
        for fn in fns:
            def wrap(fn=fn):
                try: out.append(fn())
                except Exception as e: out.append(e)
                finally: connection.close()
            ts.append(threading.Thread(target=wrap))
        [t.start() for t in ts]; [t.join() for t in ts]
        return out

    def test_concurrent_expiry_runs_restore_once(self):
        p, u = make_product(stock=10), make_user()
        expired_order(u, p, 4)
        res = self._run([services.expire_unpaid_orders for _ in range(6)])
        self.assertFalse([r for r in res if isinstance(r, Exception)], res)
        p.refresh_from_db()
        self.assertEqual(p.stock_quantity, 10)
        self.assertEqual(StockMovement.objects.filter(kind='released').count(), 1)

    def test_concurrent_cancels_restore_once(self):
        p, u, admin = make_product(stock=10), make_user(), make_user('adm@example.com', staff=True)
        o, _ = services.create_order(user=u, items=[(p.id, 3)], customer_name='A', customer_phone='08011111111', delivery_method='pickup')
        res = self._run([lambda: services.cancel_order(o.pk, by=admin) for _ in range(6)])
        self.assertFalse([r for r in res if isinstance(r, Exception)], res)
        p.refresh_from_db(); self.assertEqual(p.stock_quantity, 10)

    def test_concurrent_checkout_with_same_idempotency_key_makes_one_order(self):
        p, u = make_product(stock=10), make_user()
        res = self._run([lambda: services.create_order(user=u, items=[(p.id, 1)], customer_name='A', customer_phone='08011111111', delivery_method='pickup', idempotency_key='same') for _ in range(6)])
        self.assertFalse([r for r in res if isinstance(r, Exception)], res)
        self.assertEqual(Order.objects.count(), 1)
        p.refresh_from_db(); self.assertEqual(p.stock_quantity, 9)

    def test_many_buyers_two_products_no_oversell_no_deadlock(self):
        a, b = make_product('A', stock=4), make_product('B', stock=4)
        users = [make_user(f'u{i}@example.com') for i in range(12)]
        def buy(u, items):
            return lambda: services.create_order(user=u, items=items, customer_name='x', customer_phone='08011111111', delivery_method='pickup')
        fns = [buy(u, [(a.id, 1), (b.id, 1)] if i % 2 else [(b.id, 1), (a.id, 1)]) for i, u in enumerate(users)]
        res = self._run(fns)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual(sum(1 for r in res if isinstance(r, tuple)), 4)  # exactly 4 succeed
        self.assertEqual((a.stock_quantity, b.stock_quantity), (0, 0))
