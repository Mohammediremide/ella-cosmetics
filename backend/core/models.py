from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models


class StoreSettings(models.Model):
    """Singleton row (pk=1). All business-specific values live here, never in source code."""
    store_name = models.CharField(max_length=80, default='Ella Cosmetics')
    announcement = models.CharField(max_length=160, default='Your beauty essentials, thoughtfully selected.', blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    instagram_url = models.URLField(blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True, default='2348088317529', help_text='International format, digits only, e.g. 2348088317529')
    bank_name = models.CharField(max_length=80, blank=True)
    account_name = models.CharField(max_length=120, blank=True)
    account_number = models.CharField(max_length=20, blank=True)
    currency_symbol = models.CharField(max_length=4, default='₦')
    delivery_enabled = models.BooleanField(default=False)
    pickup_enabled = models.BooleanField(default=True)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(0)])
    pickup_instructions = models.CharField(max_length=240, blank=True)
    default_low_stock_threshold = models.PositiveIntegerField(default=5)
    new_arrival_days = models.PositiveIntegerField(default=30)
    unpaid_order_hours = models.PositiveIntegerField(default=24, validators=[MinValueValidator(1)], help_text='Unpaid orders are cancelled and stock released after this many hours')
    # Owner-provided business information for the legal pages (blank = page shows an "owner to complete" notice)
    legal_business_name = models.CharField(max_length=160, blank=True)
    business_address = models.CharField(max_length=240, blank=True)
    delivery_terms = models.TextField(blank=True, help_text='Delivery areas, timelines and charges, in your own words')
    returns_terms = models.TextField(blank=True, help_text='Your returns / exchanges / refunds policy, in your own words')

    class Meta:
        verbose_name_plural = 'store settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PageView(models.Model):
    """Privacy-friendly visit log: no IP address, no cookie. visitor = daily-rotating salted hash of IP+browser,
    so we can count unique visitors per day but cannot identify or follow a person."""
    day = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    path = models.CharField(max_length=200)
    visitor = models.CharField(max_length=64)

    class Meta:
        indexes = [models.Index(fields=['day', 'visitor']), models.Index(fields=['path'])]


def _video_storage():
    """Cloudinary video storage in production (when CLOUDINARY_URL is set); local disk in development."""
    import os
    if os.environ.get('CLOUDINARY_URL'):
        from cloudinary_storage.storage import VideoMediaCloudinaryStorage
        return VideoMediaCloudinaryStorage()
    from django.core.files.storage import default_storage
    return default_storage


class HeroSlide(models.Model):
    """One slide of the homepage slideshow: either a video or an image, with optional text and a button."""
    title = models.CharField(max_length=80, blank=True)
    subtitle = models.CharField(max_length=160, blank=True)
    button_label = models.CharField(max_length=40, blank=True)
    link_url = models.CharField(max_length=200, blank=True, help_text="Site path like /shop?category=makeup, or an https:// address")
    video = models.FileField(upload_to='slides/videos/', storage=_video_storage, blank=True)
    image = models.ImageField(upload_to='slides/images/', blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'id']

    @property
    def media_type(self):
        return 'video' if self.video else 'image'
