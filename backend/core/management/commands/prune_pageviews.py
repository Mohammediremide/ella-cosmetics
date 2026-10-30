from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import PageView


class Command(BaseCommand):
    help = 'Delete page-view rows older than N days (default 180) to keep the table small.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=180)

    def handle(self, *args, **o):
        n, _ = PageView.objects.filter(day__lt=timezone.localdate() - timedelta(days=o['days'])).delete()
        self.stdout.write(f'Deleted {n} page view(s).')
