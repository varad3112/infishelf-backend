"""
Views and ViewSets for Product catalog management and GenAI actions.
Keeps views thin and delegates logic to models, serializers, and services.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
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
        Public permissions for catalog reads and smart search.
        Authenticated permissions for mutations and AI description generation.
        """
        if self.action in ['list', 'retrieve', 'smart_search']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        """Associate created product with the authenticated user."""
        serializer.save(created_by=self.request.user)

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
