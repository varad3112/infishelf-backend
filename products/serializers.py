"""
Serializers for Product catalog management and GenAI actions.
"""
from decimal import Decimal
from rest_framework import serializers
from .models import Product

class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer for Product creation, update, and retrieval.
    """
    created_by_username = serializers.ReadOnlyField(source='created_by.username')

    class Meta:
        model = Product
        fields = (
            'id',
            'name',
            'brand',
            'category',
            'description',
            'price',
            'image_url',
            'tags',
            'created_by',
            'created_by_username',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'created_by',
            'created_by_username',
            'created_at',
            'updated_at',
        )

    def validate_name(self, value):
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("Product name cannot be empty.")
        return stripped

    def validate_brand(self, value):
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("Brand cannot be empty.")
        return stripped

    def validate_category(self, value):
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("Category cannot be empty.")
        return stripped

    def validate_price(self, value):
        if value is None or value < Decimal('0.01'):
            raise serializers.ValidationError("Price must be greater than or equal to $0.01.")
        return value

    def validate_image_url(self, value):
        stripped = value.strip()
        if not (stripped.startswith('http://') or stripped.startswith('https://')):
            raise serializers.ValidationError("Image URL must begin with http:// or https://.")
        return stripped

    def validate_tags(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list of strings.")
        return [str(tag).strip() for tag in value if str(tag).strip()]

class AiGenerateDescriptionSerializer(serializers.Serializer):
    """Serializer for AI description generation input."""
    name = serializers.CharField(
        max_length=255,
        required=True,
        help_text="Product commercial name"
    )
    brand = serializers.CharField(
        max_length=100,
        required=True,
        help_text="Product brand"
    )
    category = serializers.CharField(
        max_length=100,
        required=True,
        help_text="Product retail category"
    )

class AiSmartSearchSerializer(serializers.Serializer):
    """Serializer for natural language AI search input."""
    query = serializers.CharField(
        max_length=500,
        required=True,
        help_text="Natural language query (e.g. 'Sugar-free energy drinks under $5')"
    )
