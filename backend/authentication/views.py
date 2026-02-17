from rest_framework import generics, status, views, permissions
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.utils import timezone

from .serializers import SignupSerializer, CustomTokenObtainPairSerializer, UserSerializer
from .models import OTPAudit
from .services import otp as otp_service

User = get_user_model()

class SignupView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = SignupSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        refresh = RefreshToken.for_user(user)

        return Response({
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': getattr(user, 'full_name', '')
            },
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'message': 'User created successfully'
        }, status=status.HTTP_201_CREATED)

class LoginView(TokenObtainPairView):
    permission_classes = (AllowAny,)
    serializer_class = CustomTokenObtainPairSerializer

class UserMeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class SendOTPView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({"detail": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Check cooldown
        if otp_service.check_resend_cooldown(email):
            return Response({"detail": "Please wait before resending OTP"}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        otp = otp_service.generate_otp()
        otp_service.store_otp(email, otp)
        otp_service.send_otp_email(email, otp)

        # Audit
        OTPAudit.objects.create(email=email, action='SENT')

        return Response({"status": "success", "message": "OTP sent successfully"})

class VerifyOTPView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')

        if not email or not otp:
            return Response({"detail": "Email and OTP are required"}, status=status.HTTP_400_BAD_REQUEST)

        is_valid, message = otp_service.verify_otp_hash(email, otp)

        if is_valid:
            # Mark user as verified if they exist
            User.objects.filter(email=email).update(
                is_email_verified=True, 
                email_verified_at=timezone.now()
            )
            OTPAudit.objects.create(email=email, action='VERIFIED')
            return Response({"status": "success", "message": "Email verified successfully"})
        else:
            OTPAudit.objects.create(email=email, action='FAILED')
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetRequestView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({"detail": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user exists
        if not User.objects.filter(email=email).exists():
            # For security, don't reveal if user exists, but we'll return early
            return Response({"status": "success", "message": "If this email is registered, you will receive an OTP"})

        # Check cooldown
        if otp_service.check_resend_cooldown(email):
            return Response({"detail": "Please wait before requesting another OTP"}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        otp = otp_service.generate_otp()
        otp_service.store_otp(email, otp)
        otp_service.send_otp_email(email, otp)

        OTPAudit.objects.create(email=email, action='SENT')

        return Response({"status": "success", "message": "Password reset OTP sent"})

class PasswordResetConfirmView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        new_password = request.data.get('new_password')

        if not all([email, otp, new_password]):
            return Response({"detail": "Email, OTP and new password are required"}, status=status.HTTP_400_BAD_REQUEST)

        is_valid, message = otp_service.verify_otp_hash(email, otp)

        if is_valid:
            try:
                user = User.objects.get(email=email)
                user.set_password(new_password)
                user.save()
                OTPAudit.objects.create(email=email, action='VERIFIED')
                return Response({"status": "success", "message": "Password reset successfully"})
            except User.DoesNotExist:
                return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            OTPAudit.objects.create(email=email, action='FAILED')
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
