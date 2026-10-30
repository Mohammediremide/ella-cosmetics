import secrets
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

REF_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # no look-alike characters


def new_reference():
    return 'ELLA-' + ''.join(secrets.choice(REF_ALPHABET) for _ in range(8))


class Cart(models.Model):
    """Server-side cart for signed-in customers. Guests keep (product_id, qty) client-side."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    updated_at = models.DateTimeField(auto_now=True)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['cart', 'product'], name='one_line_per_product'),
            models.CheckConstraint(check=Q(quantity__gte=1), name='cart_qty_positive'),
        ]


class Order(models.Model):
    class Payment(models.TextChoices):
        AWAITING = 'awaiting_payment', 'Awaiting Payment'                       # order created, receipt not yet submitted
        SUBMITTED = 'pending_verification', 'Processing — Awaiting Verification'  # customer pressed "Done"; NOT proof of payment
        VERIFIED = 'verified', 'Payment Successful'                              # only an admin can set this
        REJECTED = 'rejected', 'Payment Rejected'

    class Fulfilment(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        DISPATCHED = 'dispatched', 'Dispatched'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'

    class Method(models.TextChoices):
        DELIVERY = 'delivery', 'Delivery'
        PICKUP = 'pickup', 'Pickup'

    reference = models.CharField(max_length=16, unique=True, default=new_reference, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    customer_name = models.CharField(max_length=120)
    customer_phone = models.CharField(max_length=20)
    delivery_method = models.CharField(max_length=10, choices=Method.choices)
    delivery_address = models.TextField(blank=True)
    note = models.CharField(max_length=500, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    payment_status = models.CharField(max_length=24, choices=Payment.choices, default=Payment.AWAITING)
    fulfilment_status = models.CharField(max_length=12, choices=Fulfilment.choices, default=Fulfilment.PENDING)
    payment_submitted_at = models.DateTimeField(null=True, blank=True)
    payment_reviewed_at = models.DateTimeField(null=True, blank=True)
    payment_reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    payment_rejection_reason = models.CharField(max_length=500, blank=True)
    idempotency_key = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['payment_status', 'fulfilment_status']), models.Index(fields=['payment_submitted_at']), models.Index(fields=['user', '-created_at'])]
        constraints = [
            # Same client retry (same key) can never create a second order
            models.UniqueConstraint(fields=['user', 'idempotency_key'], condition=~Q(idempotency_key=''), name='unique_idempotency_per_user'),
        ]

    def __str__(self):
        return self.reference


class OrderItem(models.Model):
    """Immutable snapshot: survives product edits/archival."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('catalog.Product', null=True, on_delete=models.SET_NULL)
    product_name = models.CharField(max_length=160)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)


class OrderAudit(models.Model):
    """Who changed payment/fulfilment status, and when."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='audit')
    field = models.CharField(max_length=20)
    old_value = models.CharField(max_length=30)
    new_value = models.CharField(max_length=30)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    changed_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-changed_at', '-id']
