"""
Serializers for User authentication and registration.
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

class UserSerializer(serializers.ModelSerializer):
    """Serializer for reading user information."""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'date_joined')
        read_only_fields = fields

class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration with robust validation."""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=False,
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=False,
        style={'input_type': 'password'}
    )
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'confirm_password', 'password_confirm', 'first_name', 'last_name')
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
        }

    def validate_email(self, value):
        """Ensure email is unique case-insensitively."""
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email address already exists.")
        return value.lower()

    def validate(self, attrs):
        """Ensure passwords match."""
        confirm = attrs.get('confirm_password') or attrs.get('password_confirm')
        if not confirm:
            raise serializers.ValidationError({"confirm_password": ["Password confirmation is required."]})
        if attrs.get('password') != confirm:
            raise serializers.ValidationError({"confirm_password": ["Passwords do not match."]})
        return attrs

    def create(self, validated_data):
        """Create and return a new User instance."""
        validated_data.pop('confirm_password', None)
        validated_data.pop('password_confirm', None)
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user
