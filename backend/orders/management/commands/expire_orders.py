from django.core.management.base import BaseCommand
from orders.services import expire_unpaid_orders


class Command(BaseCommand):
    help = 'Cancel unpaid orders past their reservation window and release their stock.'

    def handle(self, *args, **opts):
        self.stdout.write(f'Expired {expire_unpaid_orders()} order(s).')
