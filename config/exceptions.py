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

    # Handle unhandled database / operational exceptions gracefully so API always returns JSON, never HTML
    from django.db import DatabaseError, OperationalError, connection
    if isinstance(exc, (OperationalError, DatabaseError)):
        try:
            connection.close()
        except Exception:
            pass

        return Response(
            {
                'success': False,
                'message': 'Database connection busy or temporarily unavailable. Please try again shortly.',
                'errors': {
                    'database': [str(exc)]
                }
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    # Return standard JSON for any other uncaught API exceptions
    return Response(
        {
            'success': False,
            'message': 'An unexpected server error occurred. Please try again later.',
            'errors': {
                'server': [str(exc)]
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
