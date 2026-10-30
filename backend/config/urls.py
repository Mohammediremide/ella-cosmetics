from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.http import JsonResponse
from django.db import connection
from rest_framework.routers import DefaultRouter
from accounts import views as acc
from catalog import views as cat
from core import views as core
from core import analytics, slides
from orders import views as ords

def health(request):
    """Liveness + DB check for hosting platforms. Returns no sensitive data."""
    try:
        with connection.cursor() as c:
            c.execute('SELECT 1')
    except Exception:
        return JsonResponse({'status': 'error'}, status=503)
    return JsonResponse({'status': 'ok'})


def server_error(request):
    return JsonResponse({'error': {'code': 'server_error', 'message': 'Something went wrong on our side. Please try again.'}}, status=500)


def not_found(request, exception=None):
    return JsonResponse({'error': {'code': 'not_found', 'message': 'Not found.'}}, status=404)


handler500, handler404 = server_error, not_found
r = DefaultRouter()
r.register('orders', ords.OrderViewSet, basename='order')
ar = DefaultRouter()
ar.register('products', cat.AdminProductViewSet, basename='admin-product')
ar.register('categories', cat.AdminCategoryViewSet, basename='admin-category')
ar.register('orders', ords.AdminOrderViewSet, basename='admin-order')
ar.register('slides', slides.AdminSlideViewSet, basename='admin-slide')

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('api/health/', health),
    path('api/auth/csrf/', acc.CsrfView.as_view()),
    path('api/auth/register/', acc.RegisterView.as_view()),
    path('api/auth/login/', acc.LoginView.as_view()),
    path('api/auth/logout/', acc.LogoutView.as_view()),
    path('api/auth/me/', acc.MeView.as_view()),
    path('api/auth/password-reset/', acc.PasswordResetRequestView.as_view()),
    path('api/auth/password-reset/confirm/', acc.PasswordResetConfirmView.as_view()),
    path('api/products/', cat.ProductListView.as_view()),
    path('api/products/<slug:slug>/', cat.ProductDetailView.as_view()),
    path('api/categories/', cat.CategoryListView.as_view()),
    path('api/settings/', core.PublicSettingsView.as_view()),
    path('api/slides/', slides.SlideListView.as_view()),
    path('api/analytics/visit/', analytics.TrackVisitView.as_view()),
    path('api/admin/analytics/', analytics.AdminAnalyticsView.as_view()),
    path('api/cart/', ords.CartView.as_view()),
    path('api/cart/merge/', ords.CartMergeView.as_view()),
    path('api/cart/validate/', ords.CartValidateView.as_view()),
    path('api/checkout/', ords.CheckoutView.as_view()),
    path('api/', include(r.urls)),
    path('api/admin/overview/', ords.AdminOverviewView.as_view()),
    path('api/admin/settings/', core.AdminSettingsView.as_view()),
    path('api/admin/product-images/<int:pk>/', cat.AdminProductImageView.as_view()),
    path('api/admin/', include(ar.urls)),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
