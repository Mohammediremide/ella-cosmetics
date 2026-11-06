from django.db import transaction
from django.db.models import Count, Q, Sum
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from catalog.models import Product
from core.models import StoreSettings
from core.permissions import IsStaffUser
from . import services
from .models import Cart, CartItem, Order
from .serializers import AdminOrderSerializer, CheckoutItemSerializer, CheckoutSerializer, OrderSerializer


def price_lines(pairs):
    """[(product_id, qty)] -> live lines, clamped to stock. Browser-supplied prices are never used."""
    merged = {}
    for pid, q in pairs:
        merged[pid] = merged.get(pid, 0) + q
    products = {p.id: p for p in Product.objects.sellable().filter(id__in=merged).prefetch_related('images')}
    lines, adjusted = [], False
    for pid, q in merged.items():
        p = products.get(pid)
        if not p:
            adjusted = True
            continue
        qty = min(q, p.stock_quantity)
        adjusted |= qty != q
        if qty < 1:
            continue
        img = p.images.first()
        lines.append({'product_id': p.id, 'slug': p.slug, 'name': p.name, 'image': img.image.url if img else None,
                      'unit_price': p.price, 'quantity': qty, 'line_total': p.price * qty, 'available': p.stock_quantity})
    return {'items': lines, 'subtotal': sum((l['line_total'] for l in lines), 0), 'adjusted': adjusted}


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def _pairs(self, cart):
        return list(cart.items.values_list('product_id', 'quantity'))

    def get(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        data = price_lines(self._pairs(cart))
        self._sync(cart, data)
        return Response(data)

    def put(self, request):
        """Replace the whole cart: {items: [{product_id, quantity}]}"""
        s = CheckoutItemSerializer(data=request.data.get('items', []), many=True)
        s.is_valid(raise_exception=True)
        cart, _ = Cart.objects.get_or_create(user=request.user)
        data = price_lines([(i['product_id'], i['quantity']) for i in s.validated_data])
        self._sync(cart, data)
        return Response(data)

    def _sync(self, cart, data):
        with transaction.atomic():
            cart.items.all().delete()
            CartItem.objects.bulk_create([CartItem(cart=cart, product_id=l['product_id'], quantity=l['quantity']) for l in data['items']])


class CartMergeView(CartView):
    def post(self, request):
        """After login: add guest items to the server cart, then revalidate."""
        s = CheckoutItemSerializer(data=request.data.get('items', []), many=True)
        s.is_valid(raise_exception=True)
        cart, _ = Cart.objects.get_or_create(user=request.user)
        pairs = self._pairs(cart) + [(i['product_id'], i['quantity']) for i in s.validated_data]
        data = price_lines(pairs)
        self._sync(cart, data)
        return Response(data)


class CartValidateView(APIView):
    """Guests: price their local cart from the database."""
    permission_classes = [AllowAny]

    def post(self, request):
        s = CheckoutItemSerializer(data=request.data.get('items', []), many=True)
        s.is_valid(raise_exception=True)
        return Response(price_lines([(i['product_id'], i['quantity']) for i in s.validated_data]))


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """Customers only ever see their own orders (queryset is scoped by user => 404 for others')."""
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'reference'
    throttle_scope = 'payment_submit'  # used only by the scoped-throttled submit-payment action

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'cfg': StoreSettings.load()}

    @action(detail=True, methods=['post'], url_path='submit-payment', throttle_classes=[ScopedRateThrottle])
    def submit_payment(self, request, reference=None):
        """"Done — I've Sent the Receipt". Marks the order as awaiting admin verification; never as paid."""
        order = self.get_object()  # scoped to request.user => other customers' orders are 404
        order, _ = services.submit_payment(order.pk, by=request.user)
        order = self.get_queryset().get(pk=order.pk)
        return Response(self.get_serializer(order).data)


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = 'checkout'
    throttle_classes = [ScopedRateThrottle]

    def post(self, request):
        s = CheckoutSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if d.get('items'):
            pairs = [(i['product_id'], i['quantity']) for i in d['items']]
        else:
            cart = Cart.objects.filter(user=request.user).first()
            pairs = list(cart.items.values_list('product_id', 'quantity')) if cart else []
        order, created = services.create_order(
            user=request.user, items=pairs, customer_name=d['customer_name'], customer_phone=d['customer_phone'],
            delivery_method=d['delivery_method'], delivery_address=d.get('delivery_address', ''), note=d.get('note', ''),
            idempotency_key=request.headers.get('Idempotency-Key', '')[:64],
            dispatch_requested=d.get('dispatch_requested', False), dispatch_address=d.get('dispatch_address', ''),
            dispatch_state=d.get('dispatch_state', ''), dispatch_city=d.get('dispatch_city', ''),
            dispatch_phone=d.get('dispatch_phone', ''), dispatch_instructions=d.get('dispatch_instructions', ''))
        if created:
            Cart.objects.filter(user=request.user).first() and CartItem.objects.filter(cart__user=request.user).delete()
        out = OrderSerializer(order, context={'cfg': StoreSettings.load()}).data
        return Response(out, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


# ---------- Admin ----------
class AdminOrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsStaffUser]
    serializer_class = AdminOrderSerializer
    filterset_fields = ['payment_status', 'fulfilment_status', 'dispatch_requested']
    search_fields = ['reference', 'customer_name', 'customer_phone', 'user__email']
    ordering_fields = ['created_at', 'payment_submitted_at', 'total']
    ordering = ['-created_at']
    queryset = Order.objects.select_related('user', 'payment_reviewed_by').prefetch_related('items', 'audit__changed_by')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'cfg': StoreSettings.load()}

    def _respond(self, order):
        order = self.get_queryset().get(pk=order.pk)
        return Response(self.get_serializer(order).data)

    def perform_destroy(self, instance):
        services.delete_order(instance.pk, by=self.request.user)

    @action(detail=True, methods=['post'], url_path='payment')
    def payment(self, request, pk=None):
        return self._respond(services.set_payment_status(pk, request.data.get('status'), by=request.user, note=str(request.data.get('note', ''))[:200], reason=str(request.data.get('reason', ''))))

    @action(detail=True, methods=['post'], url_path='fulfilment')
    def fulfilment(self, request, pk=None):
        return self._respond(services.set_fulfilment_status(pk, request.data.get('status'), by=request.user, note=request.data.get('note', '')[:200]))

    @action(detail=True, methods=['post'], url_path='dispatch')
    def update_dispatch(self, request, pk=None):
        return self._respond(services.set_dispatch_status(
            pk, request.data.get('status'), by=request.user, note=str(request.data.get('note', ''))[:200]))


class AdminOverviewView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        cfg = StoreSettings.load()
        active = Product.objects.filter(is_active=True)
        low = [p for p in active.filter(stock_quantity__gt=0) if p.stock_status(cfg.default_low_stock_threshold) == 'low_stock']
        paid = Order.objects.filter(payment_status=Order.Payment.VERIFIED).exclude(fulfilment_status=Order.Fulfilment.CANCELLED)
        return Response({
            'total_products': active.count(),
            'in_stock': active.filter(stock_quantity__gt=0).count(),
            'low_stock': len(low),
            'out_of_stock': active.filter(stock_quantity=0).count(),
            'total_orders': Order.objects.count(),
            'orders_with_dispatch': Order.objects.filter(dispatch_requested=True).count(),
            'orders_without_dispatch': Order.objects.filter(dispatch_requested=False).count(),
            'awaiting_verification': Order.objects.filter(payment_status=Order.Payment.SUBMITTED).exclude(fulfilment_status=Order.Fulfilment.CANCELLED).count(),
            'awaiting_payment': Order.objects.filter(payment_status=Order.Payment.AWAITING).exclude(fulfilment_status=Order.Fulfilment.CANCELLED).count(),
            'processing': Order.objects.filter(fulfilment_status=Order.Fulfilment.PROCESSING).count(),
            'verified_sales_total': paid.aggregate(t=Sum('total'))['t'] or 0,  # only verified payments count as sales
            'recent_orders': AdminOrderSerializer(Order.objects.select_related('user', 'payment_reviewed_by').prefetch_related('items', 'audit')[:5], many=True, context={'cfg': cfg}).data,
        })
