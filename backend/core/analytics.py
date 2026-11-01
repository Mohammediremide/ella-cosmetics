"""Privacy-friendly visit counting. No cookies, no IP addresses stored; staff browsing and bots are ignored."""
import hashlib
import hmac
import re
from urllib.parse import parse_qs
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import PageView
from .permissions import IsStaffUser

BOT_WORDS = ('bot', 'spider', 'crawl', 'slurp', 'headless', 'preview', 'monitor', 'curl', 'python-requests')
# Personal pages are never logged (an order reference in a URL would be personal data)
IGNORED_PREFIXES = ('/admin', '/api', '/login', '/register', '/reset-password', '/forgot-password', '/account', '/orders')
SLUG = re.compile(r'^[a-z0-9-]{1,80}$')


def clean_path(raw):
    """Drop the #fragment and the query string, EXCEPT a valid ?category=<slug> on /shop (so section pages can be counted).
    Search words and anything else a visitor typed are never stored."""
    raw = str(raw)[:300].split('#')[0]
    path, _, query = raw.partition('?')
    path = path[:200]
    if path == '/shop':
        cat = parse_qs(query).get('category', [''])[0]
        if SLUG.match(cat):
            return f'/shop?category={cat}'
    return path


def label_for(path, products, sections):
    """Human-readable name for the 'Most viewed pages' list."""
    fixed = {'/': 'Home page', '/shop': 'All products', '/cart': 'Cart', '/checkout': 'Checkout', '/privacy': 'Privacy policy', '/terms': 'Terms of sale'}
    if path in fixed:
        return fixed[path]
    if path.startswith('/shop?category='):
        slug = path.split('=', 1)[1]
        return f'Section: {sections.get(slug, slug)}'
    if path.startswith('/shop/'):
        slug = path[len('/shop/'):]
        return f'Product: {products.get(slug, slug)}'
    return path



def _visitor(request, day):
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
    ip = fwd or request.META.get('REMOTE_ADDR', '')
    ua = request.META.get('HTTP_USER_AGENT', '')[:200]
    # Salted + date-scoped: the same person looks like a different visitor tomorrow, so nobody can be followed over time
    return hmac.new(settings.SECRET_KEY.encode(), f'{day}|{ip}|{ua}'.encode(), hashlib.sha256).hexdigest()[:32]


class TrackVisitView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'analytics'
    throttle_classes = [ScopedRateThrottle]

    def post(self, request):
        path = clean_path(request.data.get('path', ''))
        ua = request.META.get('HTTP_USER_AGENT', '').lower()
        user = request.user
        skip = (not path.startswith('/') or path.startswith(IGNORED_PREFIXES) or not ua
                or any(w in ua for w in BOT_WORDS) or (user.is_authenticated and user.is_staff))
        if not skip:
            day = timezone.localdate()
            PageView.objects.create(day=day, path=path, visitor=_visitor(request, day.isoformat()))
        return Response(status=204)


def _totals(qs):
    rows = qs.values('day').annotate(v=Count('id'), u=Count('visitor', distinct=True))
    return {'page_views': sum(r['v'] for r in rows), 'visitors': sum(r['u'] for r in rows)}


class AdminAnalyticsView(APIView):
    """visitors = unique visitors per day, summed over the period (a returning visitor counts once per day)."""
    permission_classes = [IsStaffUser]

    def get(self, request):
        try:
            days = max(1, min(int(request.query_params.get('days', 14)), 90))
        except ValueError:
            days = 14
        today = timezone.localdate()
        start = today - timedelta(days=days - 1)
        qs = PageView.objects.all()
        by_day = {r['day']: r for r in qs.filter(day__gte=start).values('day').annotate(v=Count('id'), u=Count('visitor', distinct=True))}
        series = [{'day': (start + timedelta(days=i)).isoformat(),
                   'page_views': by_day.get(start + timedelta(days=i), {}).get('v', 0),
                   'visitors': by_day.get(start + timedelta(days=i), {}).get('u', 0)} for i in range(days)]
        hidden = Q()
        for prefix in IGNORED_PREFIXES:  # a lookup takes ONE prefix, so OR them together
            hidden |= Q(path__startswith=prefix)
        top_qs = qs.filter(day__gte=start).exclude(hidden).values('path').annotate(v=Count('id')).order_by('-v')[:10]  # also hides older rows logged before these were excluded
        top = list(top_qs)
        from catalog.models import Category, Product
        slugs = [r['path'][len('/shop/'):] for r in top if r['path'].startswith('/shop/') and '?' not in r['path']]
        cats = [r['path'].split('=', 1)[1] for r in top if r['path'].startswith('/shop?category=')]
        products = dict(Product.objects.filter(slug__in=slugs).values_list('slug', 'name'))
        sections = dict(Category.objects.filter(slug__in=cats).values_list('slug', 'name'))
        return Response({
            'today': _totals(qs.filter(day=today)),
            'last_7_days': _totals(qs.filter(day__gte=today - timedelta(days=6))),
            'last_30_days': _totals(qs.filter(day__gte=today - timedelta(days=29))),
            'all_time': _totals(qs),
            'days': days, 'daily': series, 'top_pages': [{'path': r['path'], 'label': label_for(r['path'], products, sections), 'page_views': r['v']} for r in top],
        })
