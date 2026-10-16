"""
Pagination configuration for InfiShelf REST API.
"""
import math
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class StandardProductPagination(PageNumberPagination):
    """
    Standard pagination for product listings.
    Default page size is 12 (optimized for 3x4 / 4x3 desktop grid).
    """
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        total_count = self.page.paginator.count
        current_page_size = self.get_page_size(self.request) or self.page_size
        total_pages = math.ceil(total_count / current_page_size) if total_count > 0 else 1

        return Response({
            'count': total_count,
            'total_pages': total_pages,
            'current_page': self.page.number,
            'page_size': current_page_size,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })
