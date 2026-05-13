from rest_framework import renderers
import json

class CustomRenderer(renderers.JSONRenderer):
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get('response')
        
        # If the status code is an error, the data is already formatted by the exception handler
        if response.status_code >= 400:
            return super().render(data, accepted_media_type, renderer_context)

        # Success response formatting
        res = {
            'success': True,
            'message': data.get('message', 'Request successful') if isinstance(data, dict) else 'Request successful',
            'data': data
        }
        
        # If 'message' was in data, remove it from data to avoid redundancy in the final response
        if isinstance(data, dict) and 'message' in data:
            del res['data']['message']

        return super().render(res, accepted_media_type, renderer_context)
