"""
Filtering configuration for Product catalog.
"""
import django_filters
from django.db.models import Q
from .models import Product

class ProductFilter(django_filters.FilterSet):
    """
    FilterSet for Product catalog.
    Supports filtering by category, single or multiple brands, and price range.
    """
    category = django_filters.CharFilter(method='filter_category')
    brand = django_filters.CharFilter(method='filter_by_brand')
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')

    class Meta:
        model = Product
        fields = ['category', 'brand', 'min_price', 'max_price']

    def filter_category(self, queryset, name, value):
        if not value:
            return queryset
        val = value.strip()
        # Try exact case-insensitive match, or fallback to icontains
        exact_matches = queryset.filter(category__iexact=val)
        if exact_matches.exists():
            return exact_matches
        return queryset.filter(category__icontains=val)

    def filter_by_brand(self, queryset, name, value):
        """
        Support single brand or comma-separated brands (e.g., 'Unilever,P&G,Nestle').
        """
        if not value:
            return queryset

        brands = [b.strip() for b in value.split(',') if b.strip()]
        if len(brands) == 1:
            return queryset.filter(brand__iexact=brands[0])
        elif len(brands) > 1:
            q_objects = Q()
            for b in brands:
                q_objects |= Q(brand__iexact=b)
            return queryset.filter(q_objects)
        return queryset
