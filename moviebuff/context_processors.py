from django.conf import settings


def registration_enabled(request):
    return {"REGISTRATION_ENABLED": settings.REGISTRATION_ENABLED}
