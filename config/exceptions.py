"""
Custom exception handler for standardized DRF error responses.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

def custom_exception_handler(exc, context):
    """
    Standardize all API error responses to:
    {
        "success": false,
        "message": "...",
        "errors": { ... }
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        errors = {}
        message = "An error occurred during request processing."

        if isinstance(response.data, dict):
            if 'detail' in response.data:
                message = str(response.data['detail'])
                errors = {'detail': [message]}
            else:
                errors = response.data
                message = "Validation error on submitted fields."
        elif isinstance(response.data, list):
            errors = {'non_field_errors': response.data}
            message = str(response.data[0]) if response.data else message
        else:
            errors = {'error': [str(response.data)]}

        response.data = {
            'success': False,
            'message': message,
            'errors': errors
        }

    return response
