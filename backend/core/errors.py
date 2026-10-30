from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Consistent error shape: {"error": {"code", "message", "fields"?}}"""
    response = exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    if isinstance(data, dict) and 'detail' in data and len(data) == 1:
        body = {'code': getattr(exc, 'default_code', 'error'), 'message': str(data['detail'])}
    else:
        body = {'code': 'validation_error', 'message': 'Please check the highlighted fields.', 'fields': data}
    response.data = {'error': body}
    return response


def csrf_failure(request, reason=''):
    """JSON (not Django's HTML page) so the frontend can refresh its token and retry."""
    from django.http import JsonResponse
    return JsonResponse({'error': {'code': 'csrf_failed', 'message': 'CSRF Failed: please retry.'}}, status=403)
