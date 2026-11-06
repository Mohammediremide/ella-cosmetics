from rest_framework import serializers
from core.models import StoreSettings
from .models import Order, OrderItem
from .whatsapp import build_customer_url, build_support_url, build_whatsapp_url


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product_name', 'unit_price', 'quantity', 'line_total']


def payment_state(o):
    """(key, label) shown to people. Payment and fulfilment stay separate fields; only an unpaid CANCELLED order reads 'Cancelled'."""
    if o.fulfilment_status == Order.Fulfilment.CANCELLED and o.payment_status != Order.Payment.VERIFIED:
        return 'cancelled', 'Cancelled'
    return o.payment_status, o.get_payment_status_display()


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payment_status_display = serializers.SerializerMethodField()
    payment_tone = serializers.SerializerMethodField()
    fulfilment_status_display = serializers.CharField(source='get_fulfilment_status_display', read_only=True)
    dispatch_status_display = serializers.CharField(source='get_dispatch_status_display', read_only=True)
    bank = serializers.SerializerMethodField()
    whatsapp_url = serializers.SerializerMethodField()          # send the receipt
    whatsapp_support_url = serializers.SerializerMethodField()  # get help (e.g. rejected payment)

    class Meta:
        model = Order
        fields = ['reference', 'customer_name', 'customer_phone', 'delivery_method', 'delivery_address', 'dispatch_requested',
                  'dispatch_address', 'dispatch_state', 'dispatch_city', 'dispatch_phone', 'dispatch_instructions',
                  'dispatch_status', 'dispatch_status_display', 'note', 'subtotal',
                  'delivery_fee', 'total', 'payment_status', 'payment_status_display', 'payment_tone', 'payment_submitted_at',
                  'payment_reviewed_at', 'payment_rejection_reason', 'fulfilment_status', 'fulfilment_status_display',
                  'items', 'bank', 'whatsapp_url', 'whatsapp_support_url', 'created_at', 'expires_at']

    def _cfg(self):
        self.context.setdefault('cfg', StoreSettings.load())
        return self.context['cfg']

    def get_payment_status_display(self, o):
        return payment_state(o)[1]

    def get_payment_tone(self, o):
        return payment_state(o)[0]

    def get_bank(self, o):  # only to the owner (and staff), only while money is still expected
        if o.payment_status == Order.Payment.VERIFIED or o.fulfilment_status == Order.Fulfilment.CANCELLED:
            return None
        c = self._cfg()
        return {'bank_name': c.bank_name, 'account_name': c.account_name, 'account_number': c.account_number}

    def get_whatsapp_url(self, o):
        return build_whatsapp_url(o, self._cfg())

    def get_whatsapp_support_url(self, o):
        return build_support_url(o, self._cfg())


class AdminOrderSerializer(OrderSerializer):
    customer_email = serializers.EmailField(source='user.email', read_only=True)
    payment_reviewed_by = serializers.SerializerMethodField()
    customer_whatsapp_url = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    audit = serializers.SerializerMethodField()

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ['id', 'customer_email', 'payment_reviewed_by', 'customer_whatsapp_url', 'item_count', 'audit']

    def get_payment_reviewed_by(self, o):
        return o.payment_reviewed_by.email if o.payment_reviewed_by else None

    def get_customer_whatsapp_url(self, o):
        return build_customer_url(o, self._cfg())

    def get_item_count(self, o):
        return sum(i.quantity for i in o.items.all())

    def get_audit(self, o):
        return [{'field': a.field, 'from': a.old_value, 'to': a.new_value, 'by': a.changed_by.email if a.changed_by else 'system',
                 'at': a.changed_at, 'note': a.note} for a in o.audit.all()]


class CheckoutItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=99)


class CheckoutSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=120)
    customer_phone = serializers.RegexField(r'^\+?[0-9\s\-]{7,20}$', error_messages={'invalid': 'Enter a valid phone number.'})
    delivery_method = serializers.ChoiceField(choices=Order.Method.choices)
    delivery_address = serializers.CharField(required=False, allow_blank=True, max_length=500)
    dispatch_requested = serializers.BooleanField(required=False, default=False)
    dispatch_address = serializers.CharField(required=False, allow_blank=True, max_length=500)
    dispatch_state = serializers.CharField(required=False, allow_blank=True, max_length=100)
    dispatch_city = serializers.CharField(required=False, allow_blank=True, max_length=100)
    dispatch_phone = serializers.RegexField(r'^\+?[0-9\s\-]{7,20}$', required=False, allow_blank=True,
                                            error_messages={'invalid': 'Enter a valid dispatch phone number.'})
    dispatch_instructions = serializers.CharField(required=False, allow_blank=True, max_length=500)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)
    items = CheckoutItemSerializer(many=True, required=False)  # omitted => use the server-side cart

    def validate(self, attrs):
        if attrs.get('dispatch_requested'):
            required = {
                'dispatch_address': 'Enter your full delivery address.',
                'dispatch_state': 'Enter your state.',
                'dispatch_city': 'Enter your city or area.',
                'dispatch_phone': 'Enter your phone number for dispatch.',
            }
            errors = {field: [message] for field, message in required.items() if not attrs.get(field, '').strip()}
            if errors:
                raise serializers.ValidationError(errors)
        return attrs
