import io
from decimal import Decimal

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Category, Product
from core.models import StoreSettings
from orders import services


def staff():
    return User.objects.create_user(email='admin@example.com', password='Str0ng-pass!x', name='Admin', is_staff=True)


def customer(email='c@example.com'):
    return User.objects.create_user(email=email, password='Str0ng-pass!x', name='Cust')


def png(name='a.png'):
    b = io.BytesIO(); Image.new('RGB', (12, 12), (190, 120, 130)).save(b, 'PNG')
    return SimpleUploadedFile(name, b.getvalue(), content_type='image/png')


class SectionTests(TestCase):
    def setUp(self):
        cache.clear(); StoreSettings.load()
        self.admin = staff()
        self.c = APIClient(); self.c.force_login(self.admin)

    def names(self, url='/api/categories/'):
        d = APIClient().get(url).json() if url == '/api/categories/' else self.c.get(url).json()
        return [x['name'] for x in d]

    def add_product(self, section, name='Thing', stock=5, price='1000'):
        r = self.c.post('/api/admin/products/', {'name': name, 'price': price, 'stock_quantity': stock, 'category_id': section, 'description': 'd'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def test_three_default_sections_exist_in_order_and_no_others(self):
        self.assertEqual(self.names(), ['Accessories', 'Fragrance', 'Makeup'])

    def test_default_sections_migration_is_idempotent(self):
        from importlib import import_module
        from django.apps import apps
        m = import_module('catalog.migrations.0004_default_sections')
        m.create_defaults(apps, None); m.create_defaults(apps, None)
        self.assertEqual(Category.objects.count(), 3)

    def test_makeup_and_accessories_products_appear_in_their_section_only(self):
        mk, ac = Category.objects.get(name='Makeup'), Category.objects.get(name='Accessories')
        self.add_product(mk.id, 'Lip Tint'); self.add_product(ac.id, 'Hair Clip')
        pub = APIClient()
        self.assertEqual([p['name'] for p in pub.get('/api/products/?category=makeup').json()['results']], ['Lip Tint'])
        self.assertEqual([p['name'] for p in pub.get('/api/products/?category=accessories').json()['results']], ['Hair Clip'])
        self.assertEqual(pub.get('/api/products/?category=fragrance').json()['count'], 0)  # empty section => empty list, no fakes
        self.assertEqual(pub.get('/api/products/').json()['count'], 2)  # "All products"
        self.assertEqual(pub.get('/api/products/?category=makeup').json()['results'][0]['category']['name'], 'Makeup')

    def test_new_section_flows_to_dropdown_and_storefront_automatically(self):
        r = self.c.post('/api/admin/categories/', {'name': '  skincare ', 'description': 'Care for your skin'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['name'], 'skincare')
        self.assertIn('skincare', self.names())  # public nav/home
        self.assertIn('skincare', self.names('/api/admin/categories/'))  # upload dropdown source
        p = self.add_product(r.json()['id'], 'Serum')
        self.assertEqual(APIClient().get('/api/products/?category=skincare').json()['count'], 1)
        self.assertEqual(p['category']['name'], 'skincare')

    def test_section_name_rules(self):
        for bad in ('makeup', ' MAKEUP ', 'Ma  keup'.replace('  ', ' ') if False else 'maKEup'):
            r = self.c.post('/api/admin/categories/', {'name': bad}, format='json')
            self.assertEqual(r.status_code, 400, bad)
            self.assertIn('already exists', str(r.json()))
        self.assertEqual(self.c.post('/api/admin/categories/', {'name': 'A'}, format='json').status_code, 400)
        self.assertEqual(self.c.post('/api/admin/categories/', {'name': 'x' * 81}, format='json').status_code, 400)
        self.assertEqual(self.c.post('/api/admin/categories/', {'name': 'Okay', 'description': 'd' * 301}, format='json').status_code, 400)
        mk = Category.objects.get(name='Makeup')
        self.assertEqual(self.c.patch(f'/api/admin/categories/{mk.id}/', {'name': 'fragrance'}, format='json').status_code, 400)  # rename clash
        self.assertEqual(self.c.patch(f'/api/admin/categories/{mk.id}/', {'name': 'MAKEUP'}, format='json').status_code, 200)  # own name, different case: fine

    def test_db_constraint_blocks_case_variant_duplicates(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.bulk_create([Category(name='MAKEUP', slug='makeup-2')])

    def test_slug_collisions_get_unique_slugs(self):
        a = Category.objects.create(name='Eye-Liner'); b = Category.objects.create(name='Eye Liner')
        self.assertNotEqual(a.slug, b.slug)

    def test_rename_and_description_show_everywhere(self):
        fr = Category.objects.get(name='Fragrance'); p = self.add_product(fr.id, 'Perfume')
        r = self.c.patch(f'/api/admin/categories/{fr.id}/', {'name': 'Perfumes', 'description': 'Scents'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Perfumes', self.names()); self.assertNotIn('Fragrance', self.names())
        self.assertEqual(APIClient().get(f"/api/products/{p['slug']}/").json()['category']['name'], 'Perfumes')
        self.assertEqual(APIClient().get('/api/products/?category=fragrance').json()['count'], 1)  # slug is stable, links keep working

    def test_admin_changes_a_products_section(self):
        mk, fr = Category.objects.get(name='Makeup'), Category.objects.get(name='Fragrance')
        p = self.add_product(mk.id)
        r = self.c.patch(f"/api/admin/products/{p['id']}/", {'category_id': fr.id}, format='json')
        self.assertEqual(r.json()['category']['name'], 'Fragrance')
        pub = APIClient()
        self.assertEqual(pub.get('/api/products/?category=makeup').json()['count'], 0)
        self.assertEqual(pub.get('/api/products/?category=fragrance').json()['count'], 1)

    def test_product_must_have_a_valid_active_section(self):
        base = {'name': 'X', 'price': '10', 'stock_quantity': 1}
        self.assertEqual(self.c.post('/api/admin/products/', base, format='json').status_code, 400)  # none chosen
        self.assertEqual(self.c.post('/api/admin/products/', {**base, 'category_id': None}, format='json').status_code, 400)
        r = self.c.post('/api/admin/products/', {**base, 'category_id': 99999}, format='json')
        self.assertEqual(r.status_code, 400); self.assertIn('does not exist', str(r.json()))
        off = Category.objects.create(name='Hidden', is_active=False)
        r = self.c.post('/api/admin/products/', {**base, 'category_id': off.id}, format='json')
        self.assertEqual(r.status_code, 400); self.assertIn('inactive', str(r.json()))
        mk = Category.objects.get(name='Makeup'); p = self.add_product(mk.id)
        r = self.c.patch(f"/api/admin/products/{p['id']}/", {'category_id': off.id}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_deactivated_section_is_hidden_and_cannot_be_bought(self):
        mk = Category.objects.get(name='Makeup'); p = self.add_product(mk.id, 'Lip Tint', stock=5)
        cu = customer(); cc = APIClient(); cc.force_login(cu)
        cc.put('/api/cart/', {'items': [{'product_id': p['id'], 'quantity': 2}]}, format='json')
        self.assertEqual(len(cc.get('/api/cart/').json()['items']), 1)
        self.assertEqual(self.c.patch(f'/api/admin/categories/{mk.id}/', {'is_active': False}, format='json').status_code, 200)
        pub = APIClient()
        self.assertNotIn('Makeup', self.names())  # nav + home
        self.assertEqual(pub.get('/api/products/').json()['count'], 0)  # listing
        self.assertEqual(pub.get('/api/products/?category=makeup').json()['count'], 0)
        self.assertEqual(pub.get(f"/api/products/{p['slug']}/").status_code, 404)  # detail
        cart = cc.get('/api/cart/').json()  # cart validation drops it
        self.assertEqual((cart['items'], cart['adjusted']), ([], True))
        guest = pub.post('/api/cart/validate/', {'items': [{'product_id': p['id'], 'quantity': 1}]}, format='json').json()
        self.assertEqual(guest['items'], [])
        r = cc.post('/api/checkout/', {'customer_name': 'A', 'customer_phone': '08011111111', 'delivery_method': 'pickup',
                                       'items': [{'product_id': p['id'], 'quantity': 1}]}, format='json')  # bypass attempt
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Product.objects.get(pk=p['id']).stock_quantity, 5)  # nothing deducted
        # nothing was deleted
        self.assertTrue(Product.objects.filter(pk=p['id']).exists())
        # reactivate => sellable again
        self.c.patch(f'/api/admin/categories/{mk.id}/', {'is_active': True}, format='json')
        self.assertEqual(pub.get('/api/products/').json()['count'], 1)

    def test_deactivation_keeps_order_history_intact(self):
        mk = Category.objects.get(name='Makeup'); p = self.add_product(mk.id, stock=5)
        u = customer()
        o, _ = services.create_order(user=u, items=[(p['id'], 1)], customer_name='A', customer_phone='08011111111', delivery_method='pickup')
        self.c.patch(f'/api/admin/categories/{mk.id}/', {'is_active': False}, format='json')
        cu = APIClient(); cu.force_login(u)
        d = cu.get(f'/api/orders/{o.reference}/').json()
        self.assertEqual(d['items'][0]['product_name'], 'Thing')

    def test_uncategorised_legacy_products_stay_sellable(self):
        legacy = Product.objects.create(name='Legacy', price=Decimal('500'), stock_quantity=3)
        self.assertEqual(APIClient().get('/api/products/').json()['count'], 1)
        self.assertEqual(APIClient().get(f'/api/products/{legacy.slug}/').status_code, 200)

    def test_delete_blocked_when_products_exist_even_archived(self):
        mk = Category.objects.get(name='Makeup'); p = self.add_product(mk.id)
        self.assertEqual(self.c.delete(f'/api/admin/categories/{mk.id}/').status_code, 409)
        self.c.delete(f"/api/admin/products/{p['id']}/")  # archive
        self.assertEqual(self.c.delete(f'/api/admin/categories/{mk.id}/').status_code, 409)  # historical reference remains
        empty = Category.objects.get(name='Fragrance')
        self.assertEqual(self.c.delete(f'/api/admin/categories/{empty.id}/').status_code, 204)

    def test_product_counts_in_admin_and_public(self):
        mk = Category.objects.get(name='Makeup')
        self.add_product(mk.id, 'A'); b = self.add_product(mk.id, 'B')
        self.c.delete(f"/api/admin/products/{b['id']}/")
        row = [x for x in self.c.get('/api/admin/categories/').json() if x['name'] == 'Makeup'][0]
        self.assertEqual((row['product_count'], row['total_products']), (1, 2))
        pub = [x for x in APIClient().get('/api/categories/').json() if x['name'] == 'Makeup'][0]
        self.assertEqual(pub['product_count'], 1)

    def test_reorder_controls_storefront_order(self):
        ids = {c.name: c.id for c in Category.objects.all()}
        r = self.c.post('/api/admin/categories/reorder/', {'ids': [ids['Makeup'], ids['Accessories'], ids['Fragrance']]}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.names(), ['Makeup', 'Accessories', 'Fragrance'])
        for bad in ([ids['Makeup']], [ids['Makeup']] * 3, list(ids.values()) + [9999], 'nope'):
            self.assertEqual(self.c.post('/api/admin/categories/reorder/', {'ids': bad}, format='json').status_code, 400)
        self.assertEqual(self.names(), ['Makeup', 'Accessories', 'Fragrance'])  # unchanged after bad requests

    def test_new_section_is_appended_last(self):
        self.c.post('/api/admin/categories/', {'name': 'Skincare'}, format='json')
        self.assertEqual(self.names()[-1], 'Skincare')

    def test_section_image_and_cover_url(self):
        mk = Category.objects.get(name='Makeup')
        r = self.c.patch(f'/api/admin/categories/{mk.id}/', {'image': png()}, format='multipart')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(APIClient().get('/api/categories/').json()[2]['image'].startswith('/media/categories/'))

    def test_customers_and_anonymous_cannot_manage_sections(self):
        mk = Category.objects.get(name='Makeup')
        cc = APIClient(); cc.force_login(customer())
        for client in (cc, APIClient()):
            self.assertEqual(client.get('/api/admin/categories/').status_code, 403)
            self.assertEqual(client.post('/api/admin/categories/', {'name': 'Hack'}, format='json').status_code, 403)
            self.assertEqual(client.patch(f'/api/admin/categories/{mk.id}/', {'is_active': False}, format='json').status_code, 403)
            self.assertEqual(client.post('/api/admin/categories/reorder/', {'ids': []}, format='json').status_code, 403)
            self.assertEqual(client.delete(f'/api/admin/categories/{mk.id}/').status_code, 403)
        mk.refresh_from_db(); self.assertTrue(mk.is_active)

    def test_public_categories_hide_inactive_and_admin_field_leaks(self):
        Category.objects.create(name='Secret', is_active=False)
        rows = APIClient().get('/api/categories/').json()
        self.assertNotIn('Secret', [r['name'] for r in rows])
        self.assertNotIn('is_active', rows[0]); self.assertNotIn('sort_order', rows[0])

    def test_existing_checkout_still_works_in_a_section(self):
        mk = Category.objects.get(name='Makeup'); p = self.add_product(mk.id, stock=3, price='2500')
        cu = customer(); cc = APIClient(); cc.force_login(cu)
        r = cc.post('/api/checkout/', {'customer_name': 'A', 'customer_phone': '08011111111', 'delivery_method': 'pickup',
                                       'items': [{'product_id': p['id'], 'quantity': 2}]}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Decimal(r.json()['total']), Decimal('5000.00'))
        self.assertEqual(Product.objects.get(pk=p['id']).stock_quantity, 1)
