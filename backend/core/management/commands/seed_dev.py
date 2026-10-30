"""LOCAL DEVELOPMENT ONLY. Creates clearly-labelled EXAMPLE products; these are not the business's real inventory."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from catalog.models import Category, Product
from core.models import StoreSettings

EXAMPLES = {  # keys must match the default sections created by the catalog migration
    'Makeup': [('Example Satin Lipstick', 8500, 12), ('Example Soft Matte Foundation', 14500, 8), ('Example Setting Powder', 9500, 0)],
    'Fragrance': [('Example Eau de Parfum', 25000, 6)],
    'Accessories': [('Example Makeup Brush Set', 7000, 15)],
}


class Command(BaseCommand):
    help = 'Create example categories/products for local development (refuses to run when DEBUG is off).'

    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError('seed_dev only runs with DJANGO_DEBUG=true.')
        for i, (cat, items) in enumerate(EXAMPLES.items()):
            c = Category.objects.get(name__iexact=cat)
            for name, price, stock in items:
                Product.objects.get_or_create(name=name, defaults={'price': price, 'stock_quantity': stock, 'category': c,
                                              'description': 'Example product for local development only.', 'is_featured': stock > 5})
        cfg = StoreSettings.load()
        cfg.pickup_enabled = True
        cfg.save()
        self.stdout.write(self.style.SUCCESS('Seeded example data. Set real bank/WhatsApp details in the admin settings page.'))
