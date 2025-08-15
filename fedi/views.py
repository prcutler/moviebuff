from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse, Http404, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import urlparse
from math import ceil
import json
import re

from .models import FediFollower, FediActivity
from .utils import HttpSignatureError, post_activity, verify_http_signature

PAGE_SIZE = 10


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


def outbox(request, username):
    """Return a paginated outbox for a local user."""
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
    activities = actor.activities.order_by("-created_at")
    total = activities.count()
    page = request.GET.get("page")

    if page:
        try:
            page = int(page)
        except ValueError:
            raise Http404
        last_page = max(1, ceil(total / PAGE_SIZE)) if total else 1
        start = (page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        items = [a.payload for a in activities[start:end]]
        data = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": f"{actor.outbox_url}?page={page}",
            "type": "OrderedCollectionPage",
            "partOf": actor.outbox_url,
            "orderedItems": items,
        }
        if page < last_page:
            data["next"] = f"{actor.outbox_url}?page={page + 1}"
        if page > 1:
            data["prev"] = f"{actor.outbox_url}?page={page - 1}"
        return JsonResponse(data, content_type="application/activity+json")

    last_page = max(1, ceil(total / PAGE_SIZE)) if total else 1
    data = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": actor.outbox_url,
        "type": "OrderedCollection",
        "totalItems": total,
        "first": f"{actor.outbox_url}?page=1",
        "last": f"{actor.outbox_url}?page={last_page}",
    }
    return JsonResponse(data, content_type="application/activity+json")


def followers(request, username):
    """Return a paginated followers collection for a local user."""
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
    followers_qs = actor.followers.filter(state=FediFollower.ACCEPTED).order_by("-created_at")
    total = followers_qs.count()
    page = request.GET.get("page")

    if page:
        try:
            page = int(page)
        except ValueError:
            raise Http404
        last_page = max(1, ceil(total / PAGE_SIZE)) if total else 1
        start = (page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        items = [f.remote_actor_id for f in followers_qs[start:end]]
        data = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": f"{actor.followers_url}?page={page}",
            "type": "CollectionPage",
            "partOf": actor.followers_url,
            "items": items,
        }
        if page < last_page:
            data["next"] = f"{actor.followers_url}?page={page + 1}"
        if page > 1:
            data["prev"] = f"{actor.followers_url}?page={page - 1}"
        return JsonResponse(data, content_type="application/activity+json")

    last_page = max(1, ceil(total / PAGE_SIZE)) if total else 1
    data = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": actor.followers_url,
        "type": "Collection",
        "totalItems": total,
        "first": f"{actor.followers_url}?page=1",
        "last": f"{actor.followers_url}?page={last_page}",
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

