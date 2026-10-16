"""
Product data models for InfiShelf.
"""
import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator

class Product(models.Model):
    """
    Model representing a retail/CPG product in the InfiShelf catalog.
    """
    objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique product identifier (UUIDv4)"
    )
    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Commercial name of the product"
    )
    brand = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Manufacturer/Brand (e.g., Unilever, Nestlé, Coca-Cola)"
    )
    category = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Retail aisle or category (e.g., Beverages & Energy Drinks, Snacks)"
    )
    description = models.TextField(
        help_text="Comprehensive product narrative and features"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Unit price in USD (must be >= 0.01)"
    )
    image_url = models.CharField(
        max_length=1000,
        help_text="Public HTTPS URL or relative local path pointing to the product image"
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Product tags and semantic keywords"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        help_text="User who created this product record"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the product was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the product was last updated"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', 'brand'], name='idx_prod_cat_brand'),
            models.Index(fields=['-created_at'], name='idx_prod_created_at'),
            models.Index(fields=['price'], name='idx_prod_price'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(price__gte=Decimal('0.01')),
                name='check_prod_price_positive'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.brand}) - ${self.price}"
