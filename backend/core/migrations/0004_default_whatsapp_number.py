from django.db import migrations

DEFAULT = '2348088317529'


def fill_blank_only(apps, schema_editor):
    # Never overwrite a number the business already saved; only fill a blank one.
    S = apps.get_model('core', 'StoreSettings')
    S.objects.filter(whatsapp_number='').update(whatsapp_number=DEFAULT)


class Migration(migrations.Migration):
    dependencies = [('core', '0003_alter_storesettings_whatsapp_number_pageview')]
    operations = [migrations.RunPython(fill_blank_only, migrations.RunPython.noop)]
