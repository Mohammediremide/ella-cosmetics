from django.db import migrations


def forward(apps, schema_editor):
    # Old "awaiting_verification" meant "created, nothing submitted": that is the new "awaiting_payment"
    apps.get_model('orders', 'Order').objects.filter(payment_status='awaiting_verification').update(payment_status='awaiting_payment')


def backward(apps, schema_editor):
    apps.get_model('orders', 'Order').objects.filter(payment_status__in=['awaiting_payment', 'pending_verification']).update(payment_status='awaiting_verification')


class Migration(migrations.Migration):
    dependencies = [('orders', '0002_order_payment_rejection_reason_and_more')]
    operations = [migrations.RunPython(forward, backward)]
