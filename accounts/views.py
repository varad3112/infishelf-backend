"""
Views for User authentication and registration.
"""
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import RegisterSerializer, UserSerializer, CustomTokenObtainPairSerializer

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Login endpoint that accepts either username or email address.
    """
    serializer_class = CustomTokenObtainPairSerializer

class RegisterView(generics.CreateAPIView):
    """
    Register a new user account.
    """
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    @extend_schema(
        summary="Register a new user",
        description="Creates a new user account with username, email, and password.",
        responses={
            201: OpenApiResponse(
                description="User registered successfully",
                response=UserSerializer
            ),
            400: OpenApiResponse(description="Validation error")
        }
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user_data = UserSerializer(user).data
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "success": True,
                "message": "User registered successfully.",
                "user": user_data,
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                }
            },
            status=status.HTTP_201_CREATED
        )

class CurrentUserView(generics.RetrieveAPIView):
    """
    Retrieve details of currently authenticated user.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    @extend_schema(
        summary="Get current user profile",
        description="Retrieves the profile of the user currently authenticated via JWT.",
        responses={
            200: UserSerializer,
            401: OpenApiResponse(description="Unauthorized - Invalid or missing token")
        }
    )
    def get_object(self):
        return self.request.user
