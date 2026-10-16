"""
Views and ViewSets for Product catalog management and GenAI actions.
Keeps views thin and delegates logic to models, serializers, and services.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db.models import Count, Avg, Min, Max, Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from .models import Product
from .serializers import (
    ProductSerializer,
    AiGenerateDescriptionSerializer,
    AiSmartSearchSerializer
)
from .filters import ProductFilter
from .services import ai_service
from config.pagination import StandardProductPagination

class ProductViewSet(viewsets.ModelViewSet):
    """
    ModelViewSet for full CRUD operations, advanced filtering,
    search, sorting, and GenAI features for retail/CPG products.
    """
    queryset = Product.objects.select_related('created_by').all()
    serializer_class = ProductSerializer
    pagination_class = StandardProductPagination
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_class = ProductFilter
    search_fields = ['name', 'brand', 'description']
    ordering_fields = ['price', 'created_at', 'name']
    ordering = ['-created_at']

    def get_permissions(self):
        """
        Public permissions for catalog reads, statistics, and smart search.
        Authenticated permissions for mutations and AI description generation.
        """
        if self.action in ['list', 'retrieve', 'smart_search', 'statistics']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        """Associate created product with the authenticated user and invalidate catalog stats cache."""
        serializer.save(created_by=self.request.user)
        from django.core.cache import cache
        cache.delete("catalog:statistics")

    def perform_update(self, serializer):
        """Update product and invalidate catalog stats cache."""
        serializer.save()
        from django.core.cache import cache
        cache.delete("catalog:statistics")

    def perform_destroy(self, instance):
        """Delete product and invalidate catalog stats cache."""
        instance.delete()
        from django.core.cache import cache
        cache.delete("catalog:statistics")

    @extend_schema(
        summary="List products",
        description="Retrieve a paginated list of products with support for search, filtering, and sorting.",
        parameters=[
            OpenApiParameter('category', str, description="Filter by category (e.g. 'Beverages & Energy Drinks')"),
            OpenApiParameter('brand', str, description="Filter by brand or comma-separated brands (e.g. 'Coca-Cola,Ferrero')"),
            OpenApiParameter('min_price', float, description="Minimum price filter"),
            OpenApiParameter('max_price', float, description="Maximum price filter"),
            OpenApiParameter('search', str, description="Case-insensitive keyword search in name, brand, or description"),
            OpenApiParameter('ordering', str, description="Sort order: 'price', '-price', 'name', '-name', 'created_at', '-created_at'"),
            OpenApiParameter('page', int, description="Page number (default 1)"),
            OpenApiParameter('page_size', int, description="Page size (default 12, max 100)"),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Create product",
        description="Create a new product record. Requires JWT authentication.",
        responses={201: ProductSerializer}
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {
                "success": True,
                "message": "Product created successfully.",
                "data": serializer.data
            },
            status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Retrieve product",
        description="Retrieve full details of a specific product by its UUID.",
        responses={200: ProductSerializer}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Update product",
        description="Update all fields of an existing product. Requires JWT authentication.",
        responses={200: ProductSerializer}
    )
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            "success": True,
            "message": "Product updated successfully.",
            "data": serializer.data
        })

    @extend_schema(
        summary="Partial update product",
        description="Partially update fields of an existing product. Requires JWT authentication.",
        responses={200: ProductSerializer}
    )
    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, partial=True, **kwargs)

    @extend_schema(
        summary="Delete product",
        description="Permanently delete a product. Requires JWT authentication.",
        responses={204: OpenApiResponse(description="Product deleted successfully")}
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {
                "success": True,
                "message": "Product deleted successfully."
            },
            status=status.HTTP_204_NO_CONTENT
        )

    @extend_schema(
        summary="AI: Generate Product Description",
        description="Generates an engaging, SEO-optimized product description and tags using Google Gemini GenAI. Requires JWT authentication.",
        request=AiGenerateDescriptionSerializer,
        responses={200: OpenApiResponse(description="Generated description and tags")}
    )
    @action(detail=False, methods=['post'], url_path='ai/generate-description', permission_classes=[IsAuthenticated])
    def generate_description(self, request):
        serializer = AiGenerateDescriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = ai_service.generate_product_description(
            name=serializer.validated_data['name'],
            brand=serializer.validated_data['brand'],
            category=serializer.validated_data['category']
        )
        return Response({"success": True, "data": result}, status=status.HTTP_200_OK)

    @extend_schema(
        summary="AI: Natural Language Smart Search",
        description="Parses natural language product queries (e.g. 'energy drinks under $5') and executes smart search.",
        request=AiSmartSearchSerializer,
        responses={200: ProductSerializer(many=True)}
    )
    @action(detail=False, methods=['post'], url_path='ai/smart-search', permission_classes=[AllowAny])
    def smart_search(self, request):
        serializer = AiSmartSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        parsed_filters = ai_service.parse_natural_language_query(serializer.validated_data['query'])
        qs = ai_service.build_smart_search_queryset(self.get_queryset(), parsed_filters)

        # Handle pagination
        page = self.paginate_queryset(qs)
        if page is not None:
            serialized_page = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serialized_page.data)
            response.data['parsed_intent'] = parsed_filters
            return response

        serializer = self.get_serializer(qs, many=True)
        return Response({
            "success": True,
            "parsed_intent": parsed_filters,
            "results": serializer.data
        })

    @extend_schema(
        summary="Catalog Statistics & Analytics",
        description="Returns KPIs, category distributions, brand stats, and price tiers for the dashboard. Cached with Redis for high performance.",
        responses={200: OpenApiResponse(description="Catalog analytics and statistics")}
    )
    @action(detail=False, methods=['get'], url_path='statistics', permission_classes=[AllowAny])
    def statistics(self, request):
        from django.core.cache import cache
        cache_key = "catalog:statistics"
        cached_stats = cache.get(cache_key)
        if cached_stats is not None:
            return Response(cached_stats)

        qs = Product.objects.all()
        total_products = qs.count()

        if total_products == 0:
            empty_stats = {
                "success": True,
                "total_products": 0,
                "total_categories": 0,
                "total_brands": 0,
                "average_price": 0,
                "min_price": 0,
                "max_price": 0,
                "total_inventory_value": 0,
                "category_distribution": [],
                "brand_distribution": [],
                "price_ranges": [],
                "recent_products": []
            }
            cache.set(cache_key, empty_stats, timeout=600)
            return Response(empty_stats)

        aggs = qs.aggregate(
            avg_price=Avg('price'),
            min_price=Min('price'),
            max_price=Max('price'),
            total_value=Sum('price')
        )

        categories_data = (
            qs.values('category')
            .annotate(count=Count('id'), avg_price=Avg('price'))
            .order_by('-count')
        )
        category_distribution = [
            {
                "category": c['category'],
                "count": c['count'],
                "percentage": round((c['count'] / total_products) * 100, 1),
                "avg_price": round(float(c['avg_price'] or 0), 2)
            }
            for c in categories_data
        ]

        brands_data = (
            qs.values('brand')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        brand_distribution = [
            {"brand": b['brand'], "count": b['count']}
            for b in brands_data
        ]

        price_ranges = [
            {"label": "Under Rs. 50", "count": qs.filter(price__lt=50).count()},
            {"label": "Rs. 50 - Rs. 150", "count": qs.filter(price__gte=50, price__lt=150).count()},
            {"label": "Rs. 150 - Rs. 300", "count": qs.filter(price__gte=150, price__lt=300).count()},
            {"label": "Above Rs. 300", "count": qs.filter(price__gte=300).count()},
        ]

        recent = (
            qs.order_by('-created_at')[:5]
            .values('id', 'name', 'brand', 'category', 'price', 'image_url', 'created_at')
        )

        data = {
            "success": True,
            "total_products": total_products,
            "total_categories": len(category_distribution),
            "total_brands": qs.values('brand').distinct().count(),
            "average_price": round(float(aggs['avg_price'] or 0), 2),
            "min_price": round(float(aggs['min_price'] or 0), 2),
            "max_price": round(float(aggs['max_price'] or 0), 2),
            "total_inventory_value": round(float(aggs['total_value'] or 0), 2),
            "category_distribution": category_distribution,
            "brand_distribution": brand_distribution,
            "price_ranges": price_ranges,
            "recent_products": list(recent)
        }
        cache.set(cache_key, data, timeout=600)  # Cached for 10 minutes
        return Response(data)

    @extend_schema(
        summary="Upload Product Image",
        description="Uploads a local packshot image file to the server and returns its public URL. Requires JWT.",
        responses={201: OpenApiResponse(description="Image uploaded successfully")}
    )
    @action(detail=False, methods=['post'], url_path='upload-image', permission_classes=[IsAuthenticated])
    def upload_image(self, request):
        file_obj = request.FILES.get('image')
        if not file_obj:
            return Response(
                {"success": False, "error": "No image file provided in request."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not file_obj.content_type.startswith('image/'):
            return Response(
                {"success": False, "error": "Uploaded file must be an image."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Max 5MB file check
        if file_obj.size > 5 * 1024 * 1024:
            return Response(
                {"success": False, "error": "Image size exceeds maximum limit of 5MB."},
                status=status.HTTP_400_BAD_REQUEST
            )

        import os, uuid
        from django.conf import settings
        from django.core.files.storage import default_storage

        ext = os.path.splitext(file_obj.name)[1].lower() or '.jpg'
        if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
            return Response(
                {"success": False, "error": "Only JPEG, PNG, and WebP images are allowed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify image integrity with Pillow to prevent Stored XSS / corrupted files
        try:
            from PIL import Image
            img = Image.open(file_obj)
            img.verify()
            file_obj.seek(0)
        except Exception:
            return Response(
                {"success": False, "error": "Invalid or corrupted image file."},
                status=status.HTTP_400_BAD_REQUEST
            )

        filename = f"products/{uuid.uuid4().hex[:12]}{ext}"
        saved_name = default_storage.save(filename, file_obj)

        image_url = request.build_absolute_uri(settings.MEDIA_URL + saved_name)

        return Response({
            "success": True,
            "message": "Image uploaded successfully.",
            "image_url": image_url,
            "relative_url": settings.MEDIA_URL + saved_name
        }, status=status.HTTP_201_CREATED)

