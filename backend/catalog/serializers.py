from django.db import transaction
from rest_framework import serializers
from core.models import StoreSettings
from .models import Category, Product, ProductImage, StockMovement

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP'}


def validate_image_file(f):
    """Size cap + content sniffing (never trust the filename or declared content type)."""
    from PIL import Image
    if f.size > MAX_IMAGE_BYTES:
        raise serializers.ValidationError('Image must be 5 MB or smaller.')
    try:
        img = Image.open(f)
        fmt, (w, h) = img.format, img.size
        img.verify()  # detects truncated/corrupt files
        f.seek(0)
    except Exception:
        raise serializers.ValidationError('This file is not a valid image.')
    if fmt not in ALLOWED_FORMATS:
        raise serializers.ValidationError('Only JPEG, PNG or WebP images are allowed.')
    if w * h > MAX_IMAGE_PIXELS:
        raise serializers.ValidationError('Image dimensions are too large.')
    return f


class RelativeImageField(serializers.ImageField):
    """Return storage URLs as-is (relative '/media/..' locally, absolute https on Cloudinary) so the
    browser always loads them through the storefront origin / CDN rather than a hard-coded backend host."""
    def to_representation(self, value):
        return value.url if value else None

    def run_validation(self, data=serializers.empty):
        f = super().run_validation(data)
        return validate_image_file(f) if hasattr(f, 'size') else f


class CategoryBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'is_active']


class CategorySerializer(serializers.ModelSerializer):
    """Customer-facing section (only active ones are ever listed)."""
    image = RelativeImageField(read_only=True)
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'image', 'product_count']

    def get_product_count(self, c):
        return getattr(c, 'live_count', None) if hasattr(c, 'live_count') else c.products.sellable().count()


class AdminCategorySerializer(serializers.ModelSerializer):
    """A store section as the admin manages it."""
    image = RelativeImageField(required=False, allow_null=True)
    product_count = serializers.SerializerMethodField()
    total_products = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'image', 'sort_order', 'is_active', 'product_count', 'total_products']
        read_only_fields = ['slug', 'sort_order']  # order changes only through the reorder endpoint

    def get_product_count(self, c):  # active (non-archived) products
        return getattr(c, 'active_count', None) if hasattr(c, 'active_count') else c.products.filter(is_active=True).count()

    def get_total_products(self, c):  # including archived: decides whether the section may be deleted
        return getattr(c, 'all_count', None) if hasattr(c, 'all_count') else c.products.count()

    def validate_name(self, v):
        v = ' '.join(str(v).split())
        if len(v) < 2:
            raise serializers.ValidationError('Section name must be at least 2 characters.')
        if len(v) > 80:
            raise serializers.ValidationError('Section name must be 80 characters or fewer.')
        clash = Category.objects.filter(name__iexact=v)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError('A section with this name already exists.')
        return v

    def validate_description(self, v):
        v = ' '.join(str(v).split())
        if len(v) > 300:
            raise serializers.ValidationError('Description must be 300 characters or fewer.')
        return v


class ProductImageSerializer(serializers.ModelSerializer):
    image = RelativeImageField()

    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'sort_order']


class ProductSerializer(serializers.ModelSerializer):
    """Public, read-only representation. Status/NEW are computed from real data."""
    category = CategoryBriefSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    stock_status = serializers.SerializerMethodField()
    is_new = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'description', 'price', 'category', 'images', 'stock_quantity',
                  'stock_status', 'is_new', 'is_featured', 'is_upcoming', 'created_at']

    def _cfg(self):
        if 'cfg' not in self.context:
            self.context['cfg'] = StoreSettings.load()
        return self.context['cfg']

    def get_stock_status(self, p):
        return p.stock_status(self._cfg().default_low_stock_threshold)

    def get_is_new(self, p):
        return p.is_new(self._cfg().new_arrival_days)


class AdminProductSerializer(ProductSerializer):
    category_id = serializers.PrimaryKeyRelatedField(source='category', queryset=Category.objects.all(), allow_null=True, required=False, write_only=True,
                                                     error_messages={'does_not_exist': 'This section does not exist.', 'null': 'Choose a section for this product.'})

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + ['category_id', 'low_stock_threshold', 'is_new_arrival', 'is_active', 'updated_at']
        read_only_fields = ['slug', 'created_at', 'updated_at']

    def validate_category_id(self, c):
        # Only active sections can receive a product. Keeping an existing assignment unchanged is always allowed.
        current = self.instance.category if self.instance else None
        if c is not None and not c.is_active and c != current:
            raise serializers.ValidationError('This section is inactive. Choose an active section.')
        return c

    def validate(self, data):
        if self.instance is None and not data.get('category'):
            raise serializers.ValidationError({'category_id': ['Choose a section for this product.']})
        return data

    def validate_price(self, v):
        if v < 0:
            raise serializers.ValidationError('Price cannot be negative.')
        return v

    @transaction.atomic
    def create(self, data):
        p = super().create(data)
        if p.stock_quantity:
            StockMovement.objects.create(product=p, delta=p.stock_quantity, resulting_quantity=p.stock_quantity,
                                         kind=StockMovement.Kind.INITIAL, reason='Product created', created_by=self.context['request'].user)
        return p

    @transaction.atomic
    def update(self, instance, data):
        # Re-read under lock so a concurrent order can't be overwritten by a stale form value
        locked = Product.objects.select_for_update().get(pk=instance.pk)
        new_qty = data.pop('stock_quantity', None)
        for k, v in data.items():
            setattr(locked, k, v)
        if new_qty is not None and new_qty != locked.stock_quantity:
            StockMovement.objects.create(product=locked, delta=new_qty - locked.stock_quantity, resulting_quantity=new_qty,
                                         kind=StockMovement.Kind.ADJUSTMENT, reason='Edited in product form', created_by=self.context['request'].user)
            locked.stock_quantity = new_qty
        locked.save()
        return locked


class StockAdjustSerializer(serializers.Serializer):
    delta = serializers.IntegerField()
    reason = serializers.CharField(max_length=200)

    def validate_delta(self, v):
        if v == 0:
            raise serializers.ValidationError('Change cannot be zero.')
        return v


class ImageUploadSerializer(serializers.ModelSerializer):
    image = RelativeImageField(required=False)  # optional on PATCH (alt text / order edits)

    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'sort_order']

    def validate(self, data):
        if self.instance is None and 'image' not in data:
            raise serializers.ValidationError({'image': ['Choose an image file.']})
        return data
