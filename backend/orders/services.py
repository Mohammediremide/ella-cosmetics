"""Order business rules. All stock changes happen here, inside transactions with row locks.

INVENTORY POLICY: stock is deducted (reserved) the moment an order is created. Cancelling an order, or
letting an unpaid order expire, restores the units. Verified payment does not touch stock again.
"""
from datetime import timedelta
from decimal import Decimal

import logging
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from catalog.models import Product, StockMovement
from core.models import StoreSettings
from .models import Order, OrderAudit, OrderItem

log = logging.getLogger(__name__)
F = Order.Fulfilment
ALLOWED_FULFILMENT = {
    F.PENDING: {F.PROCESSING, F.CANCELLED},
    F.PROCESSING: {F.DISPATCHED, F.CANCELLED},
    F.DISPATCHED: {F.DELIVERED},
    F.DELIVERED: set(),
    F.CANCELLED: set(),
}


def _fail(code, message, **extra):
    raise ValidationError({'detail': message, 'code': code, **extra})


def _merge(items):
    merged = {}
    for pid, qty in items:
        if qty < 1:
            _fail('invalid_quantity', 'Quantity must be at least 1.')
        merged[pid] = merged.get(pid, 0) + qty
    if not merged:
        _fail('empty_cart', 'Your cart is empty.')
    return merged


def create_order(*, user, items, customer_name, customer_phone, delivery_method, delivery_address='', note='', idempotency_key=''):
    """Returns (order, created). Prices, fees and stock are ALL read from the database, never the client."""
    try:
        with transaction.atomic():
            if idempotency_key:
                existing = Order.objects.filter(user=user, idempotency_key=idempotency_key).first()
                if existing:
                    return existing, False

            cfg = StoreSettings.load()
            if delivery_method == Order.Method.DELIVERY:
                if not cfg.delivery_enabled:
                    _fail('delivery_unavailable', 'Delivery is not available right now.')
                if not delivery_address.strip():
                    raise ValidationError({'delivery_address': ['Delivery address is required.']})
                fee = cfg.delivery_fee
            elif delivery_method == Order.Method.PICKUP:
                if not cfg.pickup_enabled:
                    _fail('pickup_unavailable', 'Pickup is not available right now.')
                fee = Decimal('0.00')
            else:
                _fail('invalid_method', 'Choose delivery or pickup.')

            wanted = _merge(items)
            # Lock rows in a stable order (by id) so concurrent checkouts cannot deadlock or oversell.
            products = {p.id: p for p in Product.objects.sellable().select_for_update(of=('self',)).filter(id__in=wanted).order_by('id')}
            problems = []
            for pid, qty in wanted.items():
                p = products.get(pid)
                if p is None:
                    problems.append({'product_id': pid, 'reason': 'unavailable'})
                elif p.stock_quantity < qty:
                    problems.append({'product_id': pid, 'name': p.name, 'reason': 'insufficient_stock', 'available': p.stock_quantity})
            if problems:
                _fail('stock_problem', 'Some items are no longer available in the quantity requested.', problems=problems)

            subtotal = sum((products[pid].price * qty for pid, qty in wanted.items()), Decimal('0.00'))
            order = Order.objects.create(
                user=user, customer_name=customer_name.strip(), customer_phone=customer_phone.strip(),
                delivery_method=delivery_method, delivery_address=delivery_address.strip(), note=note.strip(),
                subtotal=subtotal, delivery_fee=fee, total=subtotal + fee, idempotency_key=idempotency_key,
                expires_at=timezone.now() + timedelta(hours=cfg.unpaid_order_hours),
            )
            for pid, qty in wanted.items():
                p = products[pid]
                OrderItem.objects.create(order=order, product=p, product_name=p.name, unit_price=p.price, quantity=qty, line_total=p.price * qty)
                p.stock_quantity -= qty
                p.save(update_fields=['stock_quantity', 'updated_at'])
                StockMovement.objects.create(product=p, delta=-qty, resulting_quantity=p.stock_quantity,
                                             kind=StockMovement.Kind.RESERVED, reason=f'Order {order.reference}', order=order)
            return order, True
    except IntegrityError:
        # Two identical requests raced past the pre-check; the DB constraint caught the loser.
        existing = Order.objects.filter(user=user, idempotency_key=idempotency_key).first() if idempotency_key else None
        if existing:
            return existing, False
        raise


def _audit(order, field, old, new, by, note=''):
    OrderAudit.objects.create(order=order, field=field, old_value=old, new_value=new, changed_by=by, note=note)


def _expirable(order, now):
    return (order.payment_status in (Order.Payment.AWAITING, Order.Payment.REJECTED) and order.fulfilment_status == F.PENDING
            and order.expires_at is not None and order.expires_at < now)


def cancel_order(order_id, *, by, note='', only_if_expired=None):
    """Cancel and restore reserved stock exactly once.
    only_if_expired=<now> re-checks eligibility UNDER the row lock, so an admin verifying payment at the same
    moment the expiry job runs can never lose the order."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.fulfilment_status == F.CANCELLED:
            return order  # idempotent: never restore stock twice
        if only_if_expired is not None and not _expirable(order, only_if_expired):
            return order
        if order.fulfilment_status in (F.DISPATCHED, F.DELIVERED):
            _fail('cannot_cancel', 'Dispatched or delivered orders cannot be cancelled.')
        items = list(order.items.exclude(product=None))
        locked = {p.id: p for p in Product.objects.select_for_update().filter(id__in=[i.product_id for i in items]).order_by('id')}
        for item in items:
            p = locked[item.product_id]
            p.stock_quantity += item.quantity
            p.save(update_fields=['stock_quantity', 'updated_at'])
            StockMovement.objects.create(product=p, delta=item.quantity, resulting_quantity=p.stock_quantity,
                                         kind=StockMovement.Kind.RELEASED, reason=note or f'Cancelled {order.reference}', order=order, created_by=by)
        _audit(order, 'fulfilment', order.fulfilment_status, F.CANCELLED, by, note)
        order.fulfilment_status = F.CANCELLED
        order.save(update_fields=['fulfilment_status', 'updated_at'])
        return order


def submit_payment(order_id, *, by):
    """Customer pressed "Done — I've Sent the Receipt". Records the CLAIM only: it never marks the order paid and
    never touches stock. Idempotent: repeated presses change nothing and add no audit rows."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.fulfilment_status == F.CANCELLED:
            _fail('order_cancelled', 'This order was cancelled.')
        if order.payment_status == Order.Payment.VERIFIED:
            _fail('already_verified', 'This payment has already been verified.')
        if order.payment_status == Order.Payment.SUBMITTED:
            return order, False
        _audit(order, 'payment', order.payment_status, Order.Payment.SUBMITTED, by, 'Customer confirmed the receipt was sent')
        order.payment_status = Order.Payment.SUBMITTED
        order.payment_submitted_at = timezone.now()
        order.payment_reviewed_at, order.payment_reviewed_by, order.payment_rejection_reason = None, None, ''
        order.save(update_fields=['payment_status', 'payment_submitted_at', 'payment_reviewed_at', 'payment_reviewed_by',
                                  'payment_rejection_reason', 'updated_at'])
        return order, True


def set_payment_status(order_id, new_status, *, by, note='', reason=''):
    """Admin review. Verified/rejected record who and when; rejection requires a reason."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if new_status not in Order.Payment.values:
            _fail('invalid_status', 'Unknown payment status.')
        if order.fulfilment_status == F.CANCELLED:
            _fail('order_cancelled', 'Cancelled orders cannot change payment status.')
        if order.fulfilment_status != F.PENDING and new_status != Order.Payment.VERIFIED:
            _fail('payment_locked', 'Payment can no longer be reversed once the order is being processed. Cancel the order instead.')
        reason = (reason or '').strip()
        if new_status == Order.Payment.REJECTED and not reason:
            raise ValidationError({'reason': ['Enter the reason for rejecting this payment.']})
        if len(reason) > 500:
            raise ValidationError({'reason': ['Keep the reason under 500 characters.']})
        if order.payment_status == new_status and not (new_status == Order.Payment.REJECTED and reason != order.payment_rejection_reason):
            return order
        _audit(order, 'payment', order.payment_status, new_status, by, reason or note)
        order.payment_status = new_status
        now = timezone.now()
        if new_status in (Order.Payment.VERIFIED, Order.Payment.REJECTED):
            order.payment_reviewed_at, order.payment_reviewed_by = now, by
            order.payment_rejection_reason = reason if new_status == Order.Payment.REJECTED else ''
        else:  # reset to awaiting/pending: clear the previous decision
            order.payment_reviewed_at, order.payment_reviewed_by, order.payment_rejection_reason = None, None, ''
            if new_status == Order.Payment.SUBMITTED and not order.payment_submitted_at:
                order.payment_submitted_at = now
        order.save(update_fields=['payment_status', 'payment_reviewed_at', 'payment_reviewed_by', 'payment_rejection_reason', 'payment_submitted_at', 'updated_at'])
        return order


def set_fulfilment_status(order_id, new_status, *, by, note=''):
    if new_status == F.CANCELLED:
        return cancel_order(order_id, by=by, note=note)
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if new_status not in ALLOWED_FULFILMENT[order.fulfilment_status]:
            _fail('invalid_transition', f'Cannot move an order from {order.fulfilment_status} to {new_status}.')
        if order.payment_status != Order.Payment.VERIFIED:
            _fail('payment_not_verified', 'Verify the bank transfer before processing this order.')
        _audit(order, 'fulfilment', order.fulfilment_status, new_status, by, note)
        order.fulfilment_status = new_status
        order.save(update_fields=['fulfilment_status', 'updated_at'])
        return order


def expire_unpaid_orders(now=None):
    """Cancel unpaid orders past their reservation window and release their stock.
    Safe to run repeatedly or concurrently; one failing order never blocks the rest."""
    now = now or timezone.now()
    ids = list(Order.objects.filter(payment_status__in=[Order.Payment.AWAITING, Order.Payment.REJECTED],
                                    fulfilment_status=F.PENDING, expires_at__lt=now).values_list('id', flat=True))
    expired = 0
    for oid in ids:
        try:
            before = Order.objects.get(pk=oid).fulfilment_status
            after = cancel_order(oid, by=None, note='Expired: payment not verified in time', only_if_expired=now).fulfilment_status
            expired += before != F.CANCELLED and after == F.CANCELLED
        except Exception:  # noqa: BLE001 - log and continue with the other orders
            log.exception('Failed to expire order id=%s', oid)
    return expired
