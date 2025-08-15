from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse, Http404, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import urlparse
import json
import re

from .models import FediFollower
from .utils import HttpSignatureError, post_activity, verify_http_signature


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


def actor(request, username):
    """Return an ActivityPub Person for a local user."""
    if not settings.ACTIVITYPUB_ENABLED:
        raise Http404

    accept = request.META.get("HTTP_ACCEPT", "")
    if "application/activity+json" not in accept and "application/ld+json" not in accept:
        raise Http404

    User = get_user_model()
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        raise Http404

    profile = user.userprofile
    if not profile.fedi_enabled:
        raise Http404

    actor = user.fediactor
    data = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": actor.actor_id,
        "type": "Person",
        "preferredUsername": user.username,
        "inbox": actor.inbox_url,
        "outbox": actor.outbox_url,
        "followers": actor.followers_url,
        "publicKey": {
            "id": f"{actor.actor_id}#main-key",
            "owner": actor.actor_id,
            "publicKeyPem": actor.public_key_pem,
        },
    }

    return JsonResponse(data, content_type="application/activity+json")


@csrf_exempt
def inbox(request, username):
    """Handle incoming activities for a local user."""
    if not settings.ACTIVITYPUB_ENABLED:
        raise Http404
    if request.method != "POST":
        return HttpResponse(status=405)

    User = get_user_model()
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        raise Http404

    profile = user.userprofile
    actor = getattr(user, "fediactor", None)
    if not actor:
        raise Http404

    try:
        activity = json.loads(request.body)
    except Exception:
        return HttpResponse(status=400)

    try:
        remote_actor = verify_http_signature(request)
    except HttpSignatureError:
        return HttpResponse(status=401)

    activity_type = activity.get("type")
    if activity_type == "Follow" and activity.get("object") == actor.actor_id:
        inbox_url = remote_actor.get("inbox")
        shared_inbox = remote_actor.get("endpoints", {}).get("sharedInbox", "")
        if profile.fedi_enabled:
            follower, _ = FediFollower.objects.get_or_create(
                actor=actor,
                remote_actor_id=activity.get("actor"),
                defaults={"inbox": inbox_url, "shared_inbox": shared_inbox},
            )
            follower.state = FediFollower.ACCEPTED
            follower.save()
            accept = {
                "@context": "https://www.w3.org/ns/activitystreams",
                "type": "Accept",
                "actor": actor.actor_id,
                "object": activity,
            }
            if inbox_url:
                post_activity(actor, inbox_url, accept)
            return HttpResponse(status=202)
        else:
            reject = {
                "@context": "https://www.w3.org/ns/activitystreams",
                "type": "Reject",
                "actor": actor.actor_id,
                "object": activity,
            }
            if inbox_url:
                post_activity(actor, inbox_url, reject)
            return HttpResponse(status=403)
    elif activity_type == "Undo":
        obj = activity.get("object", {})
        if isinstance(obj, dict) and obj.get("type") == "Follow" and obj.get(
            "object"
        ) == actor.actor_id:
            FediFollower.objects.filter(
                actor=actor, remote_actor_id=obj.get("actor")
            ).delete()
            return HttpResponse(status=202)

    return HttpResponse(status=202)

