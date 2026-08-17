"""Publishing a Note to a member's followers.

Shared by every catalogue app, so a film and a show federate as the same
kind of post — same context, same interaction policy, same delivery path.
"""

import logging
import uuid

from django.conf import settings
from django.utils import timezone

from .models import FediActivity, FediDelivery, FediFollower
from .vocab import NOTE_CONTEXT, PUBLIC, build_interaction_policy

logger = logging.getLogger(__name__)


def create_note(user, content, url=None, attachment_url=None):
    """Create a Note by ``user`` and queue it to their accepted followers.

    Returns the FediActivity, or None when federation is off for this user.
    """
    if not settings.ACTIVITYPUB_ENABLED:
        logger.debug("create_note: ACTIVITYPUB_ENABLED is False")
        return None
    profile = getattr(user, "userprofile", None)
    if not profile or not profile.fedi_enabled:
        logger.debug("create_note: fedi_enabled is False for %s", user.username)
        return None

    actor = user.fediactor
    base = settings.ACTIVITYPUB_DOMAIN.rstrip("/")
    activity_id = f"{base}/activities/{uuid.uuid4()}"
    now = timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    note = {
        "id": activity_id,
        "type": "Note",
        "published": now,
        "attributedTo": actor.actor_id,
        "to": [PUBLIC],
        "cc": [actor.followers_url],
        "content": content,
        "mediaType": "text/html",
        "tag": [],
        "interactionPolicy": build_interaction_policy(actor),
    }
    if url:
        note["url"] = url
    if attachment_url:
        note["attachment"] = [{"type": "Image", "url": attachment_url}]

    payload = {
        "@context": NOTE_CONTEXT,
        "id": activity_id,
        "type": "Create",
        "actor": actor.actor_id,
        "to": [PUBLIC],
        "cc": [actor.followers_url],
        "object": note,
    }
    activity = FediActivity.objects.create(
        actor=actor, ap_id=activity_id, type="Create", payload=payload
    )

    followers = actor.followers.filter(state=FediFollower.ACCEPTED)
    logger.info(
        "create_note: found %d accepted followers for %s",
        followers.count(),
        user.username,
    )
    for follower in followers:
        FediDelivery.objects.create(activity=activity, follower=follower)
        logger.info("create_note: queued delivery to %s", follower.remote_actor_id)
    return activity
