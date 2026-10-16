"""
Master URL configuration for InfiShelf.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView
)

def api_health(request):
    """Simple API health check endpoint."""
    return JsonResponse({
        "status": "healthy",
        "service": "InfiShelf Backend API",
        "version": "1.0.0",
        "docs": "/api/docs/"
    })

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Administration
    path('admin/', admin.site.urls),

    # Health check
    path('', api_health, name='api_root'),
    path('api/health/', api_health, name='api_health'),

    # Core REST APIs
    path('api/auth/', include('accounts.urls')),
    path('api/products/', include('products.urls')),

    # OpenAPI 3.0 Documentation (drf-spectacular)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

