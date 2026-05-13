from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        custom_response_data = {
            'success': False,
            'message': response.data.get('detail', 'An error occurred'),
            'errors': response.data
        }
        # Remove detail from errors if it exists to avoid redundancy
        if 'detail' in custom_response_data['errors']:
            del custom_response_data['errors']['detail']
            
        response.data = custom_response_data

    return response
