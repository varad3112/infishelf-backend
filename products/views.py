"""
Views and ViewSets for Product catalog management and GenAI actions.
Keeps views thin and delegates logic to models, serializers, and services.
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db.models import Count, Avg, Min, Max, Sum, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from .models import Product
from .serializers import (
    ProductSerializer,
    AiGenerateDescriptionSerializer,
    AiSmartSearchSerializer,
    CatalogCopilotRequestSerializer
)
from .filters import ProductFilter
from .services import ai_service, catalog_copilot, csv_service
from config.pagination import StandardProductPagination

logger = logging.getLogger(__name__)

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
        Public permissions for catalog reads, statistics, smart search, and bulk template.
        Authenticated permissions for mutations, bulk upload, and AI description generation.
        """
        if self.action in ['list', 'retrieve', 'smart_search', 'statistics', 'copilot', 'bulk_template']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        """Associate created product with the authenticated user and invalidate catalog stats cache."""
        serializer.save(created_by=self.request.user)
        from django.core.cache import cache
        cache.delete("catalog:statistics")
        cache.delete_many(["catalog:statistics", "catalog:summary"])

    def perform_update(self, serializer):
        """Update product and invalidate catalog stats cache."""
        serializer.save()
        from django.core.cache import cache
        cache.delete_many(["catalog:statistics", "catalog:summary"])

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
        search_query = request.query_params.get('search', '').strip()
        queryset = self.filter_queryset(self.get_queryset())
        is_ai_fallback = False
        parsed_intent = None

        if search_query:
            if not queryset.exists():
                logger.info(
                    "🔍 [Search] Standard keyword search for '%s' returned 0 results. Triggering internal LLM semantic search fallback...",
                    search_query
                )
                try:
                    parsed_intent = ai_service.parse_natural_language_query(search_query)
                    logger.info(
                        "🧠 [LLM Search] Parsed intent for '%s': Category=%s | Brand=%s | MinPrice=%s | MaxPrice=%s | Keywords=%s | Source=%s",
                        search_query,
                        parsed_intent.get('category'),
                        parsed_intent.get('brand'),
                        parsed_intent.get('min_price'),
                        parsed_intent.get('max_price'),
                        parsed_intent.get('keywords'),
                        parsed_intent.get('source')
                    )
                    smart_qs = ai_service.build_smart_search_queryset(self.get_queryset(), parsed_intent)

                    # Also apply any active query params chosen in filters
                    category_filter = request.query_params.get('category', '').strip()
                    if category_filter and category_filter != 'All Categories':
                        smart_qs = smart_qs.filter(category__iexact=category_filter)

                    brand_filter = request.query_params.get('brand', '').strip()
                    if brand_filter:
                        brands = [b.strip() for b in brand_filter.split(',') if b.strip()]
                        if len(brands) == 1:
                            smart_qs = smart_qs.filter(brand__iexact=brands[0])
                        elif len(brands) > 1:
                            smart_qs = smart_qs.filter(brand__in=brands)

                    min_p = request.query_params.get('min_price')
                    if min_p:
                        try:
                            smart_qs = smart_qs.filter(price__gte=float(min_p))
                        except (ValueError, TypeError):
                            pass

                    max_p = request.query_params.get('max_price')
                    if max_p:
                        try:
                            smart_qs = smart_qs.filter(price__lte=float(max_p))
                        except (ValueError, TypeError):
                            pass

                    ordering = request.query_params.get('ordering')
                    if ordering:
                        smart_qs = smart_qs.order_by(ordering)

                    match_count = smart_qs.count()
                    tokens_info = parsed_intent.get('token_usage') if parsed_intent else None
                    if tokens_info:
                        logger.info(
                            "✨ [LLM Search] Retrieved %d product(s) for query '%s' | LLM Tokens: %d (Prompt: %d, Response: %d)",
                            match_count,
                            search_query,
                            tokens_info.get('total_tokens', 0),
                            tokens_info.get('prompt_tokens', 0),
                            tokens_info.get('candidate_tokens', 0)
                        )
                    else:
                        logger.info(
                            "✨ [LLM Search] Retrieved %d product(s) matching internal semantic query for '%s'.",
                            match_count,
                            search_query
                        )
                    queryset = smart_qs
                    is_ai_fallback = True
                except Exception as ex:
                    logger.error("⚠️ [LLM Search] Exception during internal LLM fallback: %s", ex, exc_info=True)
            else:
                logger.info(
                    "✅ [Search] Standard keyword search for '%s' directly matched %d product(s). No LLM needed.",
                    search_query,
                    queryset.count()
                )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            if is_ai_fallback:
                response.data['ai_fallback'] = True
                response.data['parsed_intent'] = parsed_intent
            return response

        serializer = self.get_serializer(queryset, many=True)
        resp_data = {"results": serializer.data}
        if is_ai_fallback:
            resp_data['ai_fallback'] = True
            resp_data['parsed_intent'] = parsed_intent
        return Response(resp_data)

    def _invalidate_stats_cache(self):
        from django.core.cache import cache
        cache.delete("catalog:statistics")

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._invalidate_stats_cache()

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._invalidate_stats_cache()

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        self._invalidate_stats_cache()

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
        tokens_info = result.get('token_usage')
        if tokens_info:
            logger.info(
                "🏷️ [AI Description] Generated for '%s' | LLM Tokens: %d (Prompt: %d, Completion: %d)",
                serializer.validated_data['name'],
                tokens_info.get('total_tokens', 0),
                tokens_info.get('prompt_tokens', 0),
                tokens_info.get('candidate_tokens', 0)
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
        summary="AI: Conversational Analytics Copilot",
        description="Translates plain-English catalog and business questions into safe Django ORM aggregations and returns structured answers with product cards.",
        request=CatalogCopilotRequestSerializer,
        responses={200: OpenApiResponse(description="Copilot analysis with answer, stats, and relevant product cards")}
    )
    @action(detail=False, methods=['post'], url_path='ai/copilot', permission_classes=[AllowAny])
    def copilot(self, request):
        serializer = CatalogCopilotRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_query = serializer.validated_data['query']
        history = serializer.validated_data.get('history', [])

        result = catalog_copilot.ask_catalog_copilot(user_query, history)

        tokens_info = result.get('tokens')
        if tokens_info:
            logger.info(
                "💬 [Catalog Copilot] Query '%s' -> Total LLM Tokens: %d (Prompt: %d, Completion: %d)",
                user_query,
                tokens_info.get('total_tokens', 0),
                tokens_info.get('prompt_tokens', 0),
                tokens_info.get('candidate_tokens', 0)
            )

        return Response({
            "success": True,
            "data": result
        }, status=status.HTTP_200_OK)

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

        # Consolidate metrics, price tiers, and counts into a single SQL aggregation query
        # to eliminate multiple sequential roundtrips over remote database connections.
        aggs = qs.aggregate(
            total_products=Count('id'),
            avg_price=Avg('price'),
            min_price=Min('price'),
            max_price=Max('price'),
            total_value=Sum('price'),
            total_brands=Count('brand', distinct=True),
            under_50=Count('id', filter=Q(price__lt=50)),
            from_50_to_150=Count('id', filter=Q(price__gte=50, price__lt=150)),
            from_150_to_300=Count('id', filter=Q(price__gte=150, price__lt=300)),
            above_300=Count('id', filter=Q(price__gte=300)),
        )

        total_products = aggs['total_products'] or 0

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

        categories_data = list(
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

        brands_data = list(
            qs.values('brand')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        brand_distribution = [
            {"brand": b['brand'], "count": b['count']}
            for b in brands_data
        ]

        price_ranges = [
            {"label": "Under Rs. 50", "count": aggs['under_50'] or 0},
            {"label": "Rs. 50 - Rs. 150", "count": aggs['from_50_to_150'] or 0},
            {"label": "Rs. 150 - Rs. 300", "count": aggs['from_150_to_300'] or 0},
            {"label": "Above Rs. 300", "count": aggs['above_300'] or 0},
        ]

        recent = list(
            qs.order_by('-created_at')[:5]
            .values('id', 'name', 'brand', 'category', 'price', 'image_url', 'created_at')
        )

        data = {
            "success": True,
            "total_products": total_products,
            "total_categories": len(category_distribution),
            "total_brands": aggs['total_brands'] or len(brand_distribution),
            "average_price": round(float(aggs['avg_price'] or 0), 2),
            "min_price": round(float(aggs['min_price'] or 0), 2),
            "max_price": round(float(aggs['max_price'] or 0), 2),
            "total_inventory_value": round(float(aggs['total_value'] or 0), 2),
            "category_distribution": category_distribution,
            "brand_distribution": brand_distribution,
            "price_ranges": price_ranges,
            "recent_products": recent
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

    @extend_schema(
        summary="Bulk Upload Products via CSV",
        description="Upload a CSV file containing multiple products for batch validation and creation. Requires JWT authentication.",
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'file': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'CSV file with headers: name, brand, category, price, description, image_url, tags'
                    }
                },
                'required': ['file']
            }
        },
        responses={
            201: OpenApiResponse(description="Bulk upload processed successfully with metrics and error report"),
            400: OpenApiResponse(description="Invalid request or file format")
        }
    )
    @action(detail=False, methods=['post'], url_path='bulk-upload', permission_classes=[IsAuthenticated])
    def bulk_upload(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response(
                {"success": False, "error": "No CSV file provided. Please upload a file under the 'file' field."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not file_obj.name.lower().endswith('.csv'):
            return Response(
                {"success": False, "error": "Uploaded file must be a CSV (.csv) file."},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = csv_service.parse_and_bulk_create_products(file_obj, request.user)
        if result.get('created_count', 0) > 0:
            self._invalidate_stats_cache()
        status_code = status.HTTP_201_CREATED if result.get('created_count', 0) > 0 else status.HTTP_400_BAD_REQUEST
        return Response(result, status=status_code)

    @extend_schema(
        summary="Download Sample CSV Template for Bulk Upload",
        description="Returns a starter CSV template with example CPG items for bulk catalog upload.",
        responses={200: OpenApiResponse(description="Sample CSV text/template file")}
    )
    @action(detail=False, methods=['get'], url_path='bulk-template', permission_classes=[AllowAny])
    def bulk_template(self, request):
        from django.http import HttpResponse
        csv_content = csv_service.generate_sample_csv_template()
        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="infishelf_sample_products.csv"'
        return response

