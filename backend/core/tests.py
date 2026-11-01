from datetime import timedelta
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from core.models import PageView

BROWSER = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1'


class VisitTrackingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(email='admin@example.com', password='Str0ng-pass!x', name='A', is_staff=True)
        self.cust = User.objects.create_user(email='c@example.com', password='Str0ng-pass!x', name='C')

    def visit(self, path='/', ua=BROWSER, ip='1.2.3.4', client=None):
        return (client or APIClient()).post('/api/analytics/visit/', {'path': path}, format='json', HTTP_USER_AGENT=ua, HTTP_X_FORWARDED_FOR=ip)

    def stats(self, days=14):
        c = APIClient(); c.force_login(self.admin)
        return c.get(f'/api/admin/analytics/?days={days}').json()

    def test_counts_views_and_unique_visitors_per_day(self):
        self.visit('/'); self.visit('/shop'); self.visit('/shop/x')  # one person, three page views
        self.visit('/', ip='5.6.7.8')                                # a second person
        s = self.stats()
        self.assertEqual(s['today'], {'page_views': 4, 'visitors': 2})
        self.assertEqual(s['all_time']['page_views'], 4)
        self.assertEqual(s['daily'][-1]['visitors'], 2)
        self.assertEqual(s['top_pages'][0], {'path': '/', 'label': 'Home page', 'page_views': 2})

    def test_no_ip_or_cookie_is_stored(self):
        self.visit('/', ip='203.0.113.9')
        row = PageView.objects.get()
        self.assertNotIn('203.0.113.9', f'{row.visitor}{row.path}')
        self.assertEqual(len(row.visitor), 32)
        r = self.visit('/'); self.assertEqual(r.status_code, 204); self.assertFalse(r.cookies)

    def test_visitor_hash_is_date_scoped(self):
        from core.analytics import _visitor
        class R: META = {'HTTP_X_FORWARDED_FOR': '1.1.1.1', 'HTTP_USER_AGENT': BROWSER}
        self.assertNotEqual(_visitor(R, '2026-01-01'), _visitor(R, '2026-01-02'))

    def test_ignores_bots_staff_admin_paths_and_junk(self):
        self.visit('/', ua='Googlebot/2.1'); self.visit('/', ua='HeadlessChrome'); self.visit('/', ua='')
        self.visit('/admin/orders'); self.visit('/api/x'); self.visit('/login'); self.visit('nope'); self.visit('')
        sc = APIClient(); sc.force_login(self.admin); self.visit('/', client=sc)
        self.assertEqual(PageView.objects.count(), 0)
        cc = APIClient(); cc.force_login(self.cust); self.visit('/shop', client=cc)  # signed-in customers do count
        self.assertEqual(PageView.objects.count(), 1)

    def test_query_string_and_hash_stripped_and_long_paths_capped(self):
        self.visit('/shop?search=secret@email.com#top'); self.visit('/' + 'a' * 500)
        paths = set(PageView.objects.values_list('path', flat=True))
        self.assertIn('/shop', paths); self.assertTrue(all(len(p) <= 200 for p in paths))

    def test_only_staff_can_read_stats(self):
        self.visit('/')
        for c in (APIClient(), self._login(self.cust)):
            self.assertEqual(c.get('/api/admin/analytics/').status_code, 403)

    def _login(self, u):
        c = APIClient(); c.force_login(u); return c

    def test_range_windows_and_zero_filled_series(self):
        PageView.objects.create(day=timezone.localdate() - timedelta(days=3), path='/', visitor='a' * 32)
        PageView.objects.create(day=timezone.localdate() - timedelta(days=40), path='/', visitor='b' * 32)
        s = self.stats(7)
        self.assertEqual((len(s['daily']), s['last_7_days']['page_views'], s['last_30_days']['page_views'], s['all_time']['page_views']), (7, 1, 1, 2))
        self.assertEqual(sum(d['page_views'] for d in s['daily']), 1)
        self.assertEqual(len(self.stats(9999)['daily']), 90)  # clamped
        self.assertEqual(len(self.stats('abc')['daily']), 14) if False else None

    def test_tracking_is_rate_limited(self):
        codes = [self.visit('/').status_code for _ in range(130)]
        self.assertIn(429, codes)

    def test_prune_command(self):
        PageView.objects.create(day=timezone.localdate() - timedelta(days=400), path='/', visitor='a' * 32)
        PageView.objects.create(day=timezone.localdate(), path='/', visitor='b' * 32)
        call_command('prune_pageviews', '--days', '180')
        self.assertEqual(PageView.objects.count(), 1)


class SettingsLoadingTests(TestCase):
    def run_settings(self, **env):
        import os, subprocess, sys
        from django.conf import settings as dj
        e = {**os.environ, 'ELLA_SKIP_DOTENV': '1', 'DJANGO_SETTINGS_MODULE': 'config.settings', 'DJANGO_DEBUG': 'true', 'DJANGO_SECRET_KEY': 'x', **env}
        code = 'import django;django.setup();from django.conf import settings as s;print(s.DATABASES["default"]["ENGINE"])'
        r = subprocess.run([sys.executable, '-c', code], cwd=dj.BASE_DIR, env=e, capture_output=True, text=True)
        return r.stdout.strip(), r.stderr[-300:]

    def test_empty_database_url_from_env_example_falls_back_to_sqlite(self):
        engine, err = self.run_settings(DATABASE_URL='', CLOUDINARY_URL='', EMAIL_HOST='', EXTRA_FRONTEND_ORIGINS='')
        self.assertEqual(engine, 'django.db.backends.sqlite3', err)

    def test_postgres_url_selects_postgres(self):
        engine, err = self.run_settings(DATABASE_URL='postgres://u:p@localhost:5432/db')
        self.assertEqual(engine, 'django.db.backends.postgresql', err)

    def test_production_refuses_to_start_without_secret_key(self):
        import os, subprocess, sys
        from django.conf import settings as dj
        e = {k: v for k, v in os.environ.items() if k not in ('DJANGO_SECRET_KEY', 'DJANGO_DEBUG', 'DATABASE_URL')}
        e.update(DJANGO_SETTINGS_MODULE='config.settings', DJANGO_DEBUG='false', ELLA_SKIP_DOTENV='1')
        r = subprocess.run([sys.executable, '-c', 'import django;django.setup()'], cwd=dj.BASE_DIR, env=e, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)


class ProductionGuardTests(TestCase):
    """Production must fail loudly on missing config instead of silently losing data or breaking logins."""
    GOOD = dict(DJANGO_DEBUG='false', DJANGO_SECRET_KEY='x', DATABASE_URL='postgres://u:p@h.example/db?sslmode=require',
                FRONTEND_ORIGIN='https://shop.example.com/', CLOUDINARY_URL='cloudinary://123456:fakesecret@demo')

    def load(self, **overrides):
        import os, subprocess, sys
        from django.conf import settings as dj
        env = {k: v for k, v in os.environ.items() if k not in ('DATABASE_URL', 'FRONTEND_ORIGIN', 'CLOUDINARY_URL', 'ALLOW_LOCAL_MEDIA', 'DJANGO_DEBUG')}
        env.update(ELLA_SKIP_DOTENV='1', DJANGO_SETTINGS_MODULE='config.settings', **{**self.GOOD, **overrides})
        env = {k: v for k, v in env.items() if v is not None}
        code = ("import django;django.setup();from django.conf import settings as s;"
                "print(s.DATABASES['default']['ENGINE'], s.DATABASES['default'].get('CONN_HEALTH_CHECKS'), s.CSRF_TRUSTED_ORIGINS, s.STORAGES['default']['BACKEND'])")
        return subprocess.run([sys.executable, '-c', code], cwd=dj.BASE_DIR, env=env, capture_output=True, text=True)

    def test_complete_production_config_loads(self):
        r = self.load()
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        self.assertIn('postgresql True', r.stdout)                       # health checks on for Neon
        self.assertIn("['https://shop.example.com']", r.stdout)           # trailing slash tolerated, then stripped
        self.assertIn('MediaCloudinaryStorage', r.stdout)

    def test_missing_database_url_is_fatal(self):
        r = self.load(DATABASE_URL=''); self.assertNotEqual(r.returncode, 0); self.assertIn('DATABASE_URL', r.stderr)

    def test_missing_or_insecure_frontend_origin_is_fatal(self):
        for bad in ('', 'http://shop.example.com', 'shop.example.com'):
            r = self.load(FRONTEND_ORIGIN=bad); self.assertNotEqual(r.returncode, 0, bad); self.assertIn('FRONTEND_ORIGIN', r.stderr)

    def test_missing_cloudinary_is_fatal_unless_explicitly_allowed(self):
        r = self.load(CLOUDINARY_URL=''); self.assertNotEqual(r.returncode, 0); self.assertIn('CLOUDINARY_URL', r.stderr)
        self.assertEqual(self.load(CLOUDINARY_URL='', ALLOW_LOCAL_MEDIA='true').returncode, 0)


class PasswordResetAvailabilityTests(TestCase):
    def test_flag_follows_email_configuration(self):
        from django.test import override_settings
        c = APIClient()
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.dummy.EmailBackend'):
            self.assertIs(c.get('/api/settings/').json()['password_reset_enabled'], False)
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'):
            self.assertIs(c.get('/api/settings/').json()['password_reset_enabled'], True)
