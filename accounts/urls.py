"""
URLs for accounts authentication.
"""
from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from drf_spectacular.utils import extend_schema, extend_schema_view
from .views import RegisterView, CurrentUserView, CustomTokenObtainPairView

# SimpleJWT views with Swagger schema documentation
DecoratedTokenObtainPairView = extend_schema_view(
    post=extend_schema(
        summary="User login (Obtain JWT tokens)",
        description="Takes username or email and password credentials and returns JWT access and refresh token pair."
    )
)(CustomTokenObtainPairView)

DecoratedTokenRefreshView = extend_schema_view(
    post=extend_schema(
        summary="Refresh JWT access token",
        description="Takes a valid refresh token and returns a fresh access token."
    )
)(TokenRefreshView)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('login/', DecoratedTokenObtainPairView.as_view(), name='auth_login'),
    path('refresh/', DecoratedTokenRefreshView.as_view(), name='auth_refresh'),
    path('me/', CurrentUserView.as_view(), name='auth_me'),
]
