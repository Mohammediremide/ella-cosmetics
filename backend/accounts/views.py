import logging
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.contrib.auth.password_validation import validate_password
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'phone', 'is_staff']  # never the password hash
        read_only_fields = ['id', 'email', 'is_staff']


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_email(self, v):
        v = v.lower()
        if User.objects.filter(email__iexact=v).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return v

    def validate_password(self, v):
        validate_password(v)
        return v


@method_decorator(ensure_csrf_cookie, name='dispatch')
class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'csrfToken': get_token(request)})


# DRF only checks CSRF for already-logged-in sessions; enforce it for anonymous login/register too
@method_decorator(csrf_protect, name='dispatch')
class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'auth'
    throttle_classes = [ScopedRateThrottle]

    def post(self, request):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = User.objects.create_user(**s.validated_data)  # staff flags can never come from the client
        login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name='dispatch')
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'auth'
    throttle_classes = [ScopedRateThrottle]

    def post(self, request):
        user = authenticate(request, username=request.data.get('email', '').lower(), password=request.data.get('password', ''))
        if user is None:  # same message whether the email exists or not
            return Response({'error': {'code': 'invalid_credentials', 'message': 'Incorrect email or password.'}}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """GET answers 200 with {"authenticated": false} for visitors who are not signed in (no red 403s in the browser console)."""
    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'GET' else [IsAuthenticated()]

    def get(self, request):
        return Response(UserSerializer(request.user).data if request.user.is_authenticated else {'authenticated': False})

    def patch(self, request):
        s = UserSerializer(request.user, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)


log = logging.getLogger(__name__)


@method_decorator(csrf_protect, name='dispatch')
class PasswordResetRequestView(APIView):
    """Always answers 200 (no account enumeration). Tokens come from Django's token generator: they expire
    after PASSWORD_RESET_TIMEOUT and become invalid as soon as the password changes (single use).
    The token is only ever sent by email; it is never returned in the response or written to logs."""
    permission_classes = [AllowAny]
    throttle_scope = 'password_reset'
    throttle_classes = [ScopedRateThrottle]

    def post(self, request):
        email = str(request.data.get('email', '')).strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first() if email else None
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f'{settings.FRONTEND_ORIGIN}/reset-password?uid={uid}&token={token}'
            try:
                send_mail('Reset your Ella Cosmetics password',
                          f'Hello {user.name},\n\nUse this link to choose a new password (valid for 1 hour):\n{link}\n\n'
                          'If you did not ask for this, you can ignore this email.',
                          settings.DEFAULT_FROM_EMAIL, [user.email])
            except Exception:  # noqa: BLE001
                log.exception('Password reset email failed for user id=%s', user.pk)  # id only: no email, no token
        return Response({'detail': 'If an account exists for that email, a reset link has been sent.'})


@method_decorator(csrf_protect, name='dispatch')
class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'auth'
    throttle_classes = [ScopedRateThrottle]

    def post(self, request):
        bad = Response({'error': {'code': 'invalid_token', 'message': 'This reset link is invalid or has expired. Please request a new one.'}}, status=400)
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(str(request.data.get('uid', '')))), is_active=True)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return bad
        if not default_token_generator.check_token(user, str(request.data.get('token', ''))):
            return bad
        password = request.data.get('password', '')
        try:
            validate_password(password, user)
        except Exception as e:  # django ValidationError
            return Response({'error': {'code': 'validation_error', 'message': 'Please check the highlighted fields.', 'fields': {'password': list(e.messages)}}}, status=400)
        user.set_password(password)
        user.save(update_fields=['password'])  # changes the hash => this token (and any other) is now dead
        return Response({'detail': 'Password updated. You can now sign in.'})
