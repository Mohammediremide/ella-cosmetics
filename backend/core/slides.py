import logging
from django.db import transaction
from django.db.models import Max
from rest_framework import generics, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from catalog.serializers import RelativeImageField
from .models import HeroSlide
from .permissions import IsStaffUser

log = logging.getLogger(__name__)
MAX_VIDEO_BYTES = 30 * 1024 * 1024
MAX_SLIDES = 10


def safe_delete(fieldfile):
    """Remove a stored file; a storage hiccup (e.g. Cloudinary unreachable) must never block editing or deleting the slide."""
    try:
        fieldfile.delete(save=False)
    except Exception:  # noqa: BLE001
        log.exception('Could not delete stored file %s', getattr(fieldfile, 'name', ''))


def validate_video_file(f):
    """Size cap + content sniffing: MP4/MOV ('ftyp' box) or WebM (EBML header). The filename is never trusted."""
    if f.size > MAX_VIDEO_BYTES:
        raise serializers.ValidationError('Video must be 30 MB or smaller. Compress it, or trim it to under about 20 seconds.')
    head = f.read(12)
    f.seek(0)
    if not (head[4:8] == b'ftyp' or head[:4] == b'\x1a\x45\xdf\xa3'):
        raise serializers.ValidationError('Upload an MP4 or WebM video.')
    return f


class VideoUrlField(serializers.FileField):
    def to_representation(self, value):
        return value.url if value else None


class PublicSlideSerializer(serializers.ModelSerializer):
    video = VideoUrlField(read_only=True)
    image = RelativeImageField(read_only=True)
    media_type = serializers.CharField(read_only=True)

    class Meta:
        model = HeroSlide
        fields = ['id', 'title', 'subtitle', 'button_label', 'link_url', 'media_type', 'video', 'image']


class AdminSlideSerializer(serializers.ModelSerializer):
    video = VideoUrlField(required=False, allow_null=True)
    image = RelativeImageField(required=False, allow_null=True)
    media_type = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(required=False, default=True)  # a missing form checkbox must NOT mean 'hidden'

    class Meta:
        model = HeroSlide
        fields = ['id', 'title', 'subtitle', 'button_label', 'link_url', 'media_type', 'video', 'image', 'sort_order', 'is_active']
        read_only_fields = ['sort_order']

    def validate_video(self, f):
        return validate_video_file(f) if hasattr(f, 'size') else f

    def validate_link_url(self, v):
        v = v.strip()
        if v and not ((v.startswith('/') and not v.startswith('//')) or v.startswith('https://')):
            raise serializers.ValidationError('Use a page on this site (like /shop) or a full https:// address.')
        return v

    def validate(self, data):
        new_video = hasattr(data.get('video'), 'size')
        new_image = hasattr(data.get('image'), 'size')
        if new_video and new_image:
            raise serializers.ValidationError({'video': ['Choose either a video or an image for a slide, not both.']})
        if not self.instance and not (new_video or new_image):
            raise serializers.ValidationError({'video': ['Upload a video or an image for this slide.']})
        if not self.instance and HeroSlide.objects.count() >= MAX_SLIDES:
            raise serializers.ValidationError({'video': [f'You can have up to {MAX_SLIDES} slides. Delete one first.']})
        if (data.get('button_label') or '').strip() and not (data.get('link_url', getattr(self.instance, 'link_url', '')) or '').strip():
            raise serializers.ValidationError({'link_url': ['Add a link for the button, or clear the button text.']})
        return data

    def update(self, instance, data):
        # Replacing the media: switching type clears the other one, and the old file is removed from storage
        if hasattr(data.get('video'), 'size'):
            if instance.image:
                safe_delete(instance.image)
            instance.image = ''
            if instance.video:
                safe_delete(instance.video)
        elif hasattr(data.get('image'), 'size'):
            if instance.video:
                safe_delete(instance.video)
            instance.video = ''
            if instance.image:
                safe_delete(instance.image)
        data.pop('video', None) if not hasattr(data.get('video'), 'size') else None
        data.pop('image', None) if not hasattr(data.get('image'), 'size') else None
        return super().update(instance, data)


class SlideListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicSlideSerializer
    pagination_class = None
    queryset = HeroSlide.objects.filter(is_active=True)


class AdminSlideViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaffUser]
    serializer_class = AdminSlideSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = None
    queryset = HeroSlide.objects.all()

    def perform_create(self, serializer):
        top = HeroSlide.objects.aggregate(m=Max('sort_order'))['m']
        serializer.save(sort_order=0 if top is None else top + 1)

    def perform_destroy(self, instance):
        if instance.video:
            safe_delete(instance.video)
        if instance.image:
            safe_delete(instance.image)
        instance.delete()

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        ids = request.data.get('ids')
        if not isinstance(ids, list) or len(ids) != len(set(ids)) or set(ids) != set(HeroSlide.objects.values_list('id', flat=True)):
            return Response({'error': {'code': 'invalid_order', 'message': 'Send every slide id exactly once.'}}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            for i, sid in enumerate(ids):
                HeroSlide.objects.filter(pk=sid).update(sort_order=i)
        return Response(self.get_serializer(self.get_queryset(), many=True).data)
