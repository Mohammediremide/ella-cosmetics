from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class UpgradePathTest(TransactionTestCase):
    """Existing stores keep their products/orders: migrate back to the previous schema, add old-style rows, migrate forward."""
    before = [('accounts', '0001_initial'), ('catalog', '0002_initial'), ('orders', '0001_initial'), ('core', '0002_storesettings_business_address_and_more')]
    after = [('accounts', '0001_initial'), ('catalog', '0004_default_sections'), ('orders', '0003_payment_status_values'), ('core', '0004_default_whatsapp_number')]

    def migrate(self, targets):
        ex = MigrationExecutor(connection)
        ex.migrate(targets)
        return MigrationExecutor(connection).loader.project_state(targets).apps

    def test_old_data_survives_and_is_mapped(self):
        old = self.migrate(self.before)
        User, Category, Product = old.get_model('accounts', 'User'), old.get_model('catalog', 'Category'), old.get_model('catalog', 'Product')
        Order, Item, Settings = old.get_model('orders', 'Order'), old.get_model('orders', 'OrderItem'), old.get_model('core', 'StoreSettings')
        u = User.objects.create(email='old@example.com', name='Old', password='x')
        Category.objects.all().delete()  # the test DB was created fully migrated; start from a pre-sections store
        legacy = Category.objects.create(name='Lips', slug='lips', sort_order=0)
        p = Product.objects.create(name='Old lipstick', slug='old-lipstick', price='5000.00', stock_quantity=4, category=legacy)
        o = Order.objects.create(reference='ELLA-OLDORDER', user=u, customer_name='Old', customer_phone='08011111111', delivery_method='pickup',
                                 subtotal='5000.00', total='5000.00', payment_status='awaiting_verification')
        Item.objects.create(order=o, product=p, product_name='Old lipstick', unit_price='5000.00', quantity=1, line_total='5000.00')
        Settings.objects.create(pk=1, whatsapp_number='')
        Settings.objects.filter(pk=1).update(whatsapp_number='2348011112222')  # a number the owner saved on purpose

        new = self.migrate(self.after)
        Category2, Order2, Product2, Settings2 = (new.get_model('catalog', 'Category'), new.get_model('orders', 'Order'),
                                                  new.get_model('catalog', 'Product'), new.get_model('core', 'StoreSettings'))
        self.assertEqual(Order2.objects.get(reference='ELLA-OLDORDER').payment_status, 'awaiting_payment')
        self.assertEqual(Product2.objects.get(slug='old-lipstick').stock_quantity, 4)
        names = list(Category2.objects.order_by('sort_order').values_list('name', flat=True))
        self.assertEqual(names, ['Lips', 'Accessories', 'Fragrance', 'Makeup'])  # existing kept, only the 3 missing defaults added
        self.assertEqual(Settings2.objects.get(pk=1).whatsapp_number, '2348011112222')  # not overwritten

        # leave the schema fully migrated for any test that runs after this one
        self.migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())
