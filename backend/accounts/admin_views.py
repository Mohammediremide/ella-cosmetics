"""Staff-only, read-only view of customer accounts. Everything about a customer EXCEPT credentials:
the password hash, sessions and tokens are never selected, serialised or returned."""
from django.db.models import Count, F, Max, OuterRef, Q, Subquery, Sum
from rest_framework import filters, serializers, viewsets

from core.permissions import IsStaffUser
from orders.models import Cart, Order
from orders.whatsapp import build_phone_url
from core.models import StoreSettings
from .models import User


def with_stats(qs):
    paid = Q(orders__payment_status=Order.Payment.VERIFIED) & ~Q(orders__fulfilment_status=Order.Fulfilment.CANCELLED)
    latest_phone = Order.objects.filter(user=OuterRef('pk')).order_by('-created_at').values('customer_phone')[:1]
    return qs.annotate(order_count=Count('orders', distinct=True), verified_spend=Sum('orders__total', filter=paid),
                       last_order_at=Max('orders__created_at'), latest_phone=Subquery(latest_phone))


class AdminCustomerSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    order_count = serializers.IntegerField(read_only=True)
    verified_spend = serializers.SerializerMethodField()
    last_order_at = serializers.DateTimeField(read_only=True)

    phone = serializers.SerializerMethodField()  # profile phone, else the number they gave at their latest checkout

    def get_phone(self, u):
        return u.phone or getattr(u, 'latest_phone', None) or ''

    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'phone', 'role', 'is_active', 'date_joined', 'last_login', 'order_count', 'verified_spend', 'last_order_at']

    def get_role(self, u):
        return 'staff' if u.is_staff else 'customer'

    def get_verified_spend(self, u):
        return str(u.verified_spend or 0)  # only payments an admin verified, minus cancelled orders


class AdminCustomerDetailSerializer(AdminCustomerSerializer):
    orders = serializers.SerializerMethodField()
    addresses = serializers.SerializerMethodField()
    other_phones = serializers.SerializerMethodField()
    cart = serializers.SerializerMethodField()
    whatsapp_url = serializers.SerializerMethodField()

    class Meta(AdminCustomerSerializer.Meta):
        fields = AdminCustomerSerializer.Meta.fields + ['orders', 'addresses', 'other_phones', 'cart', 'whatsapp_url']

    def get_orders(self, u):
        return [{'reference': o.reference, 'created_at': o.created_at, 'total': str(o.total), 'delivery_method': o.delivery_method,
                 'payment_status': o.payment_status, 'payment_status_display': o.get_payment_status_display(),
                 'fulfilment_status': o.fulfilment_status, 'fulfilment_status_display': o.get_fulfilment_status_display(),
                 'items': [f'{i.product_name} × {i.quantity}' for i in o.items.all()]} for o in u.orders.all()[:50]]

    def get_addresses(self, u):  # delivery addresses the customer has used, newest first
        seen, out = set(), []
        for o in u.orders.exclude(delivery_address='').order_by('-created_at'):
            a = o.delivery_address.strip()
            if a.lower() not in seen:
                seen.add(a.lower()); out.append({'address': a, 'last_used': o.created_at})
        return out

    def get_other_phones(self, u):  # numbers typed at checkout that differ from the profile phone
        own = ''.join(c for c in self.get_phone(u) if c.isdigit())
        nums = {}
        for o in u.orders.order_by('-created_at'):
            if ''.join(c for c in o.customer_phone if c.isdigit()) != own:
                nums.setdefault(o.customer_phone.strip(), None)
        return list(nums)

    def get_cart(self, u):
        cart = Cart.objects.filter(user=u).first()
        if not cart:
            return []
        return [{'name': i.product.name, 'quantity': i.quantity, 'unit_price': str(i.product.price)} for i in cart.items.select_related('product')]

    def get_whatsapp_url(self, u):
        cfg = StoreSettings.load()
        return build_phone_url(self.get_phone(u), f'Hello {u.name}, this is {cfg.store_name}.')


class NullsLastOrdering(filters.OrderingFilter):
    """Empty values (no orders, never signed in) always sort LAST. PostgreSQL puts them first on descending sorts, SQLite last."""
    def filter_queryset(self, request, queryset, view):
        terms = self.get_ordering(request, queryset, view)
        if not terms:
            return queryset
        return queryset.order_by(*[(F(t[1:]).desc(nulls_last=True) if t.startswith('-') else F(t).asc(nulls_last=True)) for t in terms])


class AdminCustomerViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsStaffUser]
    filter_backends = [filters.SearchFilter, NullsLastOrdering]
    search_fields = ['name', 'email', 'phone', 'latest_phone']
    ordering_fields = ['date_joined', 'last_login', 'order_count', 'verified_spend', 'name']
    ordering = ['-date_joined']

    def get_queryset(self):
        qs = with_stats(User.objects.all())
        role = self.request.query_params.get('role')
        if role == 'staff':
            qs = qs.filter(is_staff=True)
        elif role == 'customer':
            qs = qs.filter(is_staff=False)
        return qs

    def get_serializer_class(self):
        return AdminCustomerDetailSerializer if self.action == 'retrieve' else AdminCustomerSerializer
