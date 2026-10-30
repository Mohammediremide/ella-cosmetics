from django.db import migrations

DEFAULTS = ['Accessories', 'Fragrance', 'Makeup']


def create_defaults(apps, schema_editor):
    """Idempotent: skips any section that already exists (case-insensitive) so re-running never duplicates."""
    Category = apps.get_model('catalog', 'Category')
    existing = {c.name.strip().lower() for c in Category.objects.all()}
    order = (Category.objects.order_by('-sort_order').values_list('sort_order', flat=True).first())
    order = 0 if order is None else order + 1
    for name in DEFAULTS:
        if name.lower() in existing:
            continue
        Category.objects.create(name=name, slug=name.lower(), sort_order=order, is_active=True)
        order += 1


class Migration(migrations.Migration):
    dependencies = [('catalog', '0003_category_description_and_more')]
    operations = [migrations.RunPython(create_defaults, migrations.RunPython.noop)]
