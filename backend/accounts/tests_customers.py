import json
from decimal import Decimal
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Category, Product
from core.models import StoreSettings
from orders import services
from orders.models import Cart, CartItem


class AdminCustomerTests(TestCase):
    def setUp(self):
        cache.clear(); cfg = StoreSettings.load(); cfg.delivery_enabled = True; cfg.save()
        self.admin = User.objects.create_user(email='admin@example.com', password='Adm1n-Secret#pw', name='Boss', is_staff=True)
        self.ada = User.objects.create_user(email='ada@example.com', password='Ada-Secret#pw1', name='Ada Obi', phone='08031234567')
        self.bob = User.objects.create_user(email='bob@example.com', password='Bob-Secret#pw1', name='Bob Eze')
        self.p = Product.objects.create(name='Lip Tint', price=Decimal('5000'), stock_quantity=50, category=Category.objects.get(name='Makeup'))
        self.c = APIClient(); self.c.force_login(self.admin)

    def order(self, user, qty=1, address='', phone='08031234567', pay=None, cancel=False):
        o, _ = services.create_order(user=user, items=[(self.p.id, qty)], customer_name=user.name, customer_phone=phone,
                                     delivery_method='delivery' if address else 'pickup', delivery_address=address)
        if pay: services.set_payment_status(o.pk, pay, by=self.admin, reason='test reason')
        if cancel: services.cancel_order(o.pk, by=self.admin)
        return o

    def test_staff_sees_every_account_with_full_profile(self):
        r = self.c.get('/api/admin/customers/').json()
        emails = {x['email'] for x in r['results']}
        self.assertEqual(emails, {'admin@example.com', 'ada@example.com', 'bob@example.com'})
        ada = next(x for x in r['results'] if x['email'] == 'ada@example.com')
        for k in ('id', 'name', 'email', 'phone', 'role', 'is_active', 'date_joined', 'last_login', 'order_count', 'verified_spend', 'last_order_at'):
            self.assertIn(k, ada)
        self.assertEqual((ada['name'], ada['phone'], ada['role']), ('Ada Obi', '08031234567', 'customer'))

    def test_NO_password_or_credential_data_ever_appears(self):
        self.order(self.ada, address='5 Allen Ave, Ikeja'); CartItem.objects.create(cart=Cart.objects.create(user=self.ada), product=self.p, quantity=2)
        blobs = [self.c.get('/api/admin/customers/').content.decode(), self.c.get(f'/api/admin/customers/{self.ada.pk}/').content.decode(),
                 self.c.get('/api/admin/customers/?search=ada').content.decode()]
        for b in blobs:
            low = b.lower()
            for forbidden in ('password', 'pbkdf2', 'secret#pw', 'session', 'token', 'is_superuser', 'groups', 'user_permissions'):
                self.assertNotIn(forbidden, low, forbidden)
        keys = set(json.loads(blobs[1]).keys())
        self.assertFalse(keys & {'password', 'is_superuser', 'user_permissions', 'groups'})

    def test_detail_shows_orders_addresses_phones_and_cart(self):
        self.order(self.ada, 2, address='5 Allen Ave, Ikeja', pay='verified')
        self.order(self.ada, 1, address='5 allen ave, ikeja ')            # same address, different case/spacing: listed once
        self.order(self.ada, 1, address='12 Marina, Lagos', phone='08099998888')
        CartItem.objects.create(cart=Cart.objects.create(user=self.ada), product=self.p, quantity=3)
        d = self.c.get(f'/api/admin/customers/{self.ada.pk}/').json()
        self.assertEqual(len(d['orders']), 3)
        self.assertEqual(d['orders'][0]['items'], ['Lip Tint × 1'])
        self.assertEqual([a['address'] for a in d['addresses']], ['12 Marina, Lagos', '5 allen ave, ikeja'])
        self.assertEqual(d['other_phones'], ['08099998888'])
        self.assertEqual(d['cart'], [{'name': 'Lip Tint', 'quantity': 3, 'unit_price': '5000.00'}])
        self.assertTrue(d['whatsapp_url'].startswith('https://wa.me/2348031234567?text='))

    def test_spend_counts_only_verified_uncancelled_orders(self):
        self.order(self.ada, 2, pay='verified')              # 10,000 counts
        self.order(self.ada, 1)                              # unpaid: no
        self.order(self.ada, 3, pay='verified', cancel=True) # cancelled: no
        self.order(self.ada, 1, pay='rejected')              # rejected: no
        ada = next(x for x in self.c.get('/api/admin/customers/').json()['results'] if x['email'] == 'ada@example.com')
        self.assertEqual((ada['order_count'], Decimal(ada['verified_spend'])), (4, Decimal('10000')))
        bob = next(x for x in self.c.get('/api/admin/customers/').json()['results'] if x['email'] == 'bob@example.com')
        self.assertEqual((bob['order_count'], Decimal(bob['verified_spend'])), (0, Decimal('0')))

    def test_search_filter_and_sort(self):
        self.assertEqual([x['email'] for x in self.c.get('/api/admin/customers/?search=0803').json()['results']], ['ada@example.com'])
        self.assertEqual([x['email'] for x in self.c.get('/api/admin/customers/?search=eze').json()['results']], ['bob@example.com'])
        self.assertEqual([x['email'] for x in self.c.get('/api/admin/customers/?role=staff').json()['results']], ['admin@example.com'])
        self.assertEqual(len(self.c.get('/api/admin/customers/?role=customer').json()['results']), 2)
        self.order(self.bob, 1, pay='verified')
        self.assertEqual(self.c.get('/api/admin/customers/?role=customer&ordering=-verified_spend').json()['results'][0]['email'], 'bob@example.com')

    def test_people_with_no_data_sort_last_in_both_directions(self):
        self.order(self.bob, 1, pay='verified')   # Bob spent; Ada never ordered; Ada never signed in, Bob signed in
        User.objects.filter(pk=self.bob.pk).update(last_login='2026-01-01T10:00:00Z')
        for field in ('verified_spend', 'last_login'):
            desc = [x['email'] for x in self.c.get(f'/api/admin/customers/?role=customer&ordering=-{field}').json()['results']]
            asc = [x['email'] for x in self.c.get(f'/api/admin/customers/?role=customer&ordering={field}').json()['results']]
            self.assertEqual(desc[0], 'bob@example.com', field); self.assertEqual(asc[0], 'bob@example.com' if field == 'last_login' and False else asc[0])
            self.assertEqual(desc[-1], 'ada@example.com', field)

    def test_read_only_for_everyone(self):
        for m in ('post', 'put', 'patch', 'delete'):
            self.assertEqual(getattr(self.c, m)(f'/api/admin/customers/{self.ada.pk}/', {'name': 'x'}, format='json').status_code, 405, m)
        self.assertEqual(self.c.post('/api/admin/customers/', {'email': 'x@y.com'}, format='json').status_code, 405)
        self.ada.refresh_from_db(); self.assertEqual(self.ada.name, 'Ada Obi')

    def test_only_staff_may_see_customer_data(self):
        cust = APIClient(); cust.force_login(self.ada)
        for client in (cust, APIClient()):
            self.assertEqual(client.get('/api/admin/customers/').status_code, 403)
            self.assertEqual(client.get(f'/api/admin/customers/{self.bob.pk}/').status_code, 403)

    def test_pagination(self):
        for i in range(15): User.objects.create_user(email=f'u{i}@example.com', password='Str0ng-pass!x', name=f'U{i}')
        r = self.c.get('/api/admin/customers/').json()
        self.assertEqual((r['count'], len(r['results'])), (18, 12))


class PageViewLabelTests(TestCase):
    UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(email='admin@example.com', password='Str0ng-pass!x', name='A', is_staff=True)
        self.c = APIClient(); self.c.force_login(self.admin)
        Product.objects.create(name='Velvet Lipstick', slug='velvet-lipstick', price=Decimal('100'), stock_quantity=1, category=Category.objects.get(name='Makeup'))

    def visit(self, path, ip='1.1.1.1'):
        return APIClient().post('/api/analytics/visit/', {'path': path}, format='json', HTTP_USER_AGENT=self.UA, HTTP_X_FORWARDED_FOR=ip)

    def top(self):
        return {r['label']: r['page_views'] for r in self.c.get('/api/admin/analytics/').json()['top_pages']}

    def test_readable_labels_for_home_sections_and_products(self):
        for p in ('/', '/', '/shop', '/shop?category=makeup', '/shop?category=makeup', '/shop/velvet-lipstick', '/cart', '/checkout', '/privacy'):
            self.visit(p)
        t = self.top()
        self.assertEqual(t['Home page'], 2); self.assertEqual(t['Section: Makeup'], 2); self.assertEqual(t['Product: Velvet Lipstick'], 1)
        for k in ('All products', 'Cart', 'Checkout', 'Privacy policy'): self.assertIn(k, t)

    def test_search_words_and_other_query_strings_are_never_stored(self):
        self.visit('/shop?search=my+secret+name&category=makeup'); self.visit('/shop?search=lipstick'); self.visit('/shop?category=Bad Slug!')
        from core.models import PageView
        self.assertEqual(sorted(PageView.objects.values_list('path', flat=True)), ['/shop', '/shop', '/shop?category=makeup'])

    def test_personal_pages_are_not_logged_and_old_rows_are_hidden(self):
        from django.utils import timezone
        from core.models import PageView
        for p in ('/account', '/orders/ELLA-ABCD1234', '/orders'): self.visit(p)
        self.assertEqual(PageView.objects.count(), 0)
        PageView.objects.create(day=timezone.localdate(), path='/orders/ELLA-OLD00001', visitor='a' * 32)  # logged by an older version
        PageView.objects.create(day=timezone.localdate(), path='/', visitor='b' * 32)
        self.assertEqual(list(self.top()), ['Home page'])

    def test_unknown_product_slug_falls_back_to_the_slug(self):
        self.visit('/shop/deleted-thing'); self.assertIn('Product: deleted-thing', self.top())


class PhoneFallbackTests(TestCase):
    def setUp(self):
        cache.clear(); cfg = StoreSettings.load()
        self.admin = User.objects.create_user(email='admin@example.com', password='Str0ng-pass!x', name='A', is_staff=True)
        self.u = User.objects.create_user(email='new@example.com', password='Str0ng-pass!x', name='New Customer')  # signed up without a phone
        p = Product.objects.create(name='Gloss', price=Decimal('1000'), stock_quantity=9, category=Category.objects.get(name='Makeup'))
        services.create_order(user=self.u, items=[(p.id, 1)], customer_name='New', customer_phone='08077776666', delivery_method='pickup')
        self.c = APIClient(); self.c.force_login(self.admin)

    def test_checkout_phone_is_used_when_profile_has_none(self):
        row = next(x for x in self.c.get('/api/admin/customers/').json()['results'] if x['email'] == 'new@example.com')
        self.assertEqual(row['phone'], '08077776666')
        d = self.c.get(f'/api/admin/customers/{self.u.pk}/').json()
        self.assertEqual(d['phone'], '08077776666'); self.assertEqual(d['other_phones'], [])
        self.assertIn('wa.me/2348077776666', d['whatsapp_url'])

    def test_can_search_by_the_checkout_phone_number(self):
        self.assertEqual([x['email'] for x in self.c.get('/api/admin/customers/?search=0807777').json()['results']], ['new@example.com'])

    def test_customer_with_no_phone_anywhere_has_no_whatsapp_link(self):
        d = self.c.get(f'/api/admin/customers/{self.admin.pk}/').json()
        self.assertEqual((d['phone'], d['whatsapp_url']), ('', ''))
