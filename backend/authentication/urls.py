from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    SignupView, LoginView, UserMeView, SendOTPView, VerifyOTPView,
    PasswordResetRequestView, PasswordResetConfirmView
)

urlpatterns = [
    # Core Auth
    path('signup/', SignupView.as_view(), name='auth_signup'),
    path('login/', LoginView.as_view(), name='auth_login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', UserMeView.as_view(), name='auth_me'),
    
    # OTP verification
    path('send-otp/', SendOTPView.as_view(), name='auth_send_otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='auth_verify_otp'),
    path('password-reset-request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]
