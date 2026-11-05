from datetime import timedelta
from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone
from django_filters import rest_framework as df
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from core.models import StoreSettings
from core.permissions import IsStaffUser
from .models import Category, Product, ProductImage, StockMovement
from .serializers import (AdminCategorySerializer, AdminProductSerializer, CategorySerializer, ImageUploadSerializer, ProductSerializer, StockAdjustSerializer)


class ProductFilter(df.FilterSet):
    category = df.CharFilter(field_name='category__slug')
    availability = df.ChoiceFilter(choices=[('in_stock', ''), ('out_of_stock', '')], method='filter_availability')
    featured = df.BooleanFilter(field_name='is_featured')
    new = df.BooleanFilter(method='filter_new')

    class Meta:
        model = Product
        fields = []

    def filter_availability(self, qs, name, value):
        return qs.filter(stock_quantity__gt=0) if value == 'in_stock' else qs.filter(stock_quantity=0)

    def filter_new(self, qs, name, value):
        days = StoreSettings.load().new_arrival_days
        cond = Q(is_new_arrival=True) | Q(created_at__gte=timezone.now() - timedelta(days=days))
        return qs.filter(cond) if value else qs.exclude(cond)


class ProductListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'category__name']
    ordering_fields = ['created_at', 'price']
    ordering = ['-created_at']

    def get_queryset(self):  # inactive products never leak to the storefront
        return Product.objects.sellable().select_related('category').prefetch_related('images')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'cfg': StoreSettings.load()}


class ProductDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    lookup_field = 'slug'
    queryset = Product.objects.sellable().select_related('category').prefetch_related('images')


class UpcomingProductListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    pagination_class = None

    def get_queryset(self):
        return Product.objects.filter(is_active=True, is_upcoming=True).filter(
            Q(category__isnull=True) | Q(category__is_active=True)
        ).select_related('category').prefetch_related('images')


class CategoryListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    pagination_class = None
    def get_queryset(self):
        live = Q(products__is_active=True, products__is_upcoming=False)
        return Category.objects.filter(is_active=True).annotate(live_count=Count('products', filter=live, distinct=True)).order_by('sort_order', 'name')  # Meta.ordering is ignored on aggregated queries


# ---------- Admin ----------
class AdminCategoryViewSet(viewsets.ModelViewSet):
    """Staff-only section management. Sections that still have products (even archived) can only be deactivated."""
    permission_classes = [IsStaffUser]
    serializer_class = AdminCategorySerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    pagination_class = None

    def get_queryset(self):
        return Category.objects.annotate(active_count=Count('products', filter=Q(products__is_active=True), distinct=True),
                                         all_count=Count('products', distinct=True)).order_by('sort_order', 'name')

    def perform_create(self, serializer):
        top = Category.objects.aggregate(m=Max('sort_order'))['m']
        serializer.save(sort_order=0 if top is None else top + 1)

    def destroy(self, request, *args, **kwargs):
        c = self.get_object()
        if c.products.exists():
            return Response({'error': {'code': 'section_has_products', 'message': 'This section still has products. Deactivate it instead, or move its products to another section first.'}}, status=status.HTTP_409_CONFLICT)
        c.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Body: {"ids": [3, 1, 2]} -> the whole display order, atomically."""
        ids = request.data.get('ids')
        existing = set(Category.objects.values_list('id', flat=True))
        if not isinstance(ids, list) or len(ids) != len(set(ids)) or set(ids) != existing:
            return Response({'error': {'code': 'invalid_order', 'message': 'Send every section id exactly once.'}}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            for i, cid in enumerate(ids):
                Category.objects.filter(pk=cid).update(sort_order=i)
        return Response(self.get_serializer(self.get_queryset(), many=True).data)


class AdminProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaffUser]
    serializer_class = AdminProductSerializer
    search_fields = ['name']
    filterset_class = ProductFilter
    queryset = Product.objects.all().select_related('category').prefetch_related('images')

    def destroy(self, request, *args, **kwargs):
        # Orders keep their snapshots, but archiving is the safer default than hard delete
        p = self.get_object()
        p.is_active = False
        p.save(update_fields=['is_active', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='adjust-stock')
    def adjust_stock(self, request, pk=None):
        s = StockAdjustSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        with transaction.atomic():
            p = Product.objects.select_for_update().get(pk=pk)
            new_qty = p.stock_quantity + s.validated_data['delta']
            if new_qty < 0:
                return Response({'error': {'code': 'negative_stock', 'message': 'Stock cannot go below zero.'}}, status=400)
            p.stock_quantity = new_qty
            p.save(update_fields=['stock_quantity', 'updated_at'])
            StockMovement.objects.create(product=p, delta=s.validated_data['delta'], resulting_quantity=new_qty,
                                         kind=StockMovement.Kind.ADJUSTMENT, reason=s.validated_data['reason'], created_by=request.user)
        return Response(AdminProductSerializer(p, context=self.get_serializer_context()).data)

    @action(detail=True, methods=['post'], url_path='images', parser_classes=[MultiPartParser, FormParser])
    def add_image(self, request, pk=None):
        s = ImageUploadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save(product=self.get_object())
        return Response(s.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='stock-history')
    def stock_history(self, request, pk=None):
        rows = StockMovement.objects.filter(product_id=pk)[:100]
        return Response([{'delta': m.delta, 'resulting_quantity': m.resulting_quantity, 'kind': m.kind, 'reason': m.reason,
                          'created_at': m.created_at, 'by': m.created_by.email if m.created_by else None} for m in rows])


class AdminProductImageView(generics.RetrieveUpdateDestroyAPIView):
    """PATCH with a new file replaces the image; DELETE removes it."""
    permission_classes = [IsStaffUser]
    queryset = ProductImage.objects.all()
    serializer_class = ImageUploadSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
