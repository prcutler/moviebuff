from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse, Http404
from urllib.parse import urlparse
import re


def webfinger(request):
    """Return a minimal WebFinger JRD for a local ActivityPub actor."""
    if not settings.ACTIVITYPUB_ENABLED:
        raise Http404

    resource = request.GET.get("resource")
    if not resource:
        raise Http404

    match = re.match(r"^acct:([^@]+)@([^@]+)$", resource)
    if not match:
        raise Http404
    username, domain = match.groups()

    parsed_domain = urlparse(settings.ACTIVITYPUB_DOMAIN.rstrip("/"))
    host = parsed_domain.hostname
    if domain != host:
        raise Http404

    User = get_user_model()
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        raise Http404

    profile = user.userprofile
    if not profile.fedi_enabled or not profile.fedi_discoverable:
        raise Http404

    actor_url = f"{settings.ACTIVITYPUB_DOMAIN.rstrip('/')}/users/{username}"
    data = {
        "subject": f"acct:{username}@{host}",
        "links": [
            {
                "rel": "self",
                "type": "application/activity+json",
                "href": actor_url,
            }
        ],
    }
    return JsonResponse(data, content_type="application/jrd+json")

