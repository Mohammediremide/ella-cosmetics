"""Privacy-friendly visit counting. No cookies, no IP addresses stored; staff browsing and bots are ignored."""
import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import PageView
from .permissions import IsStaffUser

BOT_WORDS = ('bot', 'spider', 'crawl', 'slurp', 'headless', 'preview', 'monitor', 'curl', 'python-requests')
IGNORED_PREFIXES = ('/admin', '/api', '/login', '/register', '/reset-password', '/forgot-password')


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
        path = str(request.data.get('path', '')).split('?')[0].split('#')[0][:200]
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
        top = qs.filter(day__gte=start).values('path').annotate(v=Count('id')).order_by('-v')[:8]
        return Response({
            'today': _totals(qs.filter(day=today)),
            'last_7_days': _totals(qs.filter(day__gte=today - timedelta(days=6))),
            'last_30_days': _totals(qs.filter(day__gte=today - timedelta(days=29))),
            'all_time': _totals(qs),
            'days': days, 'daily': series, 'top_pages': [{'path': r['path'], 'page_views': r['v']} for r in top],
        })
