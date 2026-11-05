from datetime import timedelta
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.text import slugify


class Category(models.Model):
    """A store "section" (Accessories, Fragrance, Makeup, ...). Never hard-deleted while products reference it."""
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    description = models.CharField(max_length=300, blank=True)
    image = models.ImageField(upload_to='categories/', blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'categories'
        constraints = [models.UniqueConstraint(Lower('name'), name='category_name_ci_unique')]

    def save(self, *args, **kwargs):
        self.name = ' '.join(self.name.split())
        if not self.slug:
            base = slugify(self.name)[:70] or 'section'
            slug, n = base, 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f'{base}-{n}'
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def sellable(self):
        """Active, non-upcoming products in active sections; used by listings, detail, cart and checkout."""
        return self.filter(is_active=True, is_upcoming=False).filter(Q(category__isnull=True) | Q(category__is_active=True))


class Product(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True, blank=True, max_length=180)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name='products')
    # stock_quantity = units still available to sell. Units in pending orders are ALREADY deducted
    # (reservation == deduction); cancel/expiry restores them. See orders.services.
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(null=True, blank=True, help_text='Blank = store default')
    is_featured = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False, help_text='Force NEW badge regardless of age')
    is_upcoming = models.BooleanField(default=False, help_text='Show in Coming Soon without allowing purchases')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['is_active', '-created_at']), models.Index(fields=['category', 'is_active'])]
        constraints = [models.CheckConstraint(check=Q(price__gte=0), name='product_price_non_negative')]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:150] or 'product'
            slug, n = base, 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f'{base}-{n}'
            self.slug = slug
        super().save(*args, **kwargs)

    def effective_threshold(self, default):
        return self.low_stock_threshold if self.low_stock_threshold is not None else default

    def stock_status(self, default_threshold=5):
        if self.stock_quantity <= 0:
            return 'out_of_stock'
        if self.stock_quantity <= self.effective_threshold(default_threshold):
            return 'low_stock'
        return 'in_stock'

    def is_new(self, days=30):
        return self.is_new_arrival or self.created_at >= timezone.now() - timedelta(days=days)

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=160, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']


class StockMovement(models.Model):
    """Append-only audit trail of every stock change."""
    class Kind(models.TextChoices):
        ADJUSTMENT = 'adjustment', 'Manual adjustment'
        RESERVED = 'reserved', 'Reserved by order'
        RELEASED = 'released', 'Released (cancel/expiry)'
        INITIAL = 'initial', 'Initial stock'

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='movements')
    delta = models.IntegerField()
    resulting_quantity = models.PositiveIntegerField()
    kind = models.CharField(max_length=12, choices=Kind.choices)
    reason = models.CharField(max_length=200, blank=True)
    order = models.ForeignKey('orders.Order', null=True, blank=True, on_delete=models.SET_NULL, related_name='stock_movements')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
