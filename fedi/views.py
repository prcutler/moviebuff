from django.http import JsonResponse


def webfinger(request):
    """Minimal WebFinger endpoint."""
    return JsonResponse({}, status=501)

