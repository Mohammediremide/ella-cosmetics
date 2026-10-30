from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from orders.whatsapp import normalize_wa_number
from .models import StoreSettings
from .permissions import IsStaffUser

PUBLIC_FIELDS = ['store_name', 'announcement', 'contact_email', 'contact_phone', 'instagram_url', 'whatsapp_number',
                 'currency_symbol', 'delivery_enabled', 'pickup_enabled', 'delivery_fee', 'pickup_instructions',
                 'legal_business_name', 'business_address', 'delivery_terms', 'returns_terms', 'unpaid_order_hours']


class PublicSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreSettings
        fields = PUBLIC_FIELDS  # bank details are only revealed on the customer's own order


class AdminSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreSettings
        exclude = ['id']

    def validate_whatsapp_number(self, v):
        digits = normalize_wa_number(v)  # '+234 808 831 7529' / '08088317529' -> '2348088317529'
        if v and not (8 <= len(digits) <= 15):
            raise serializers.ValidationError('Enter the number in international format, e.g. +234 808 831 7529.')
        return digits

    def validate_account_number(self, v):
        if v and not (v.isdigit() and len(v) == 10):
            raise serializers.ValidationError('Nigerian account numbers have 10 digits.')
        return v


class PublicSettingsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(PublicSettingsSerializer(StoreSettings.load()).data)


class AdminSettingsView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        return Response(AdminSettingsSerializer(StoreSettings.load()).data)

    def patch(self, request):
        s = AdminSettingsSerializer(StoreSettings.load(), data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)
