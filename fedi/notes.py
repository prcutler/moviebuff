"""Publishing a Note to a member's followers.

Shared by every catalogue app, so a film and a show federate as the same
kind of post — same context, same interaction policy, same delivery path.
"""

import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import FediActivity, FediDelivery, FediFollower
from .vocab import NOTE_CONTEXT, PUBLIC, build_interaction_policy

logger = logging.getLogger(__name__)


def _hold_seconds():
    """How long a rating waits for a review before it is delivered."""
    return getattr(settings, "FEDI_HOLD_SECONDS", 120)


def held_note_for(user, subject_key):
    """An undelivered, still-held note by ``user`` about ``subject_key``.

    Only notes inside their hold window qualify. Once the window closes the
    note is on its way to followers, and anything further becomes its own
    post rather than a silent edit of something already seen.
    """
    if not subject_key:
        return None
    return (
        FediActivity.objects.filter(
            actor__user=user,
            subject_key=subject_key,
            hold_until__gt=timezone.now(),
        )
        .exclude(deliveries__status=FediDelivery.SENT)
        .order_by("-id")
        .first()
    )


def announce(user, parts, changed, *, subject_key, url=None, attachment_url=None):
    """Publish news about ``subject_key``, folding into a held note if one waits.

    ``parts`` is the subject's whole state as ordered ``{key: html}``;
    ``changed`` names the keys that just changed. Which is used depends on
    whether anything is still held:

    * A held note is rewritten from **all** of ``parts`` — nothing has reached
      followers yet, so the post simply becomes what it should now say.
    * Otherwise only the **changed** parts are posted. Rebuilding from the
      full state there would repeat a rating that followers already saw.
    """
    held = held_note_for(user, subject_key)

    if held is not None:
        content = "<br><br>".join(html for html in parts.values() if html)
        if not content:
            return held
        note = held.payload["object"]
        note["content"] = content
        if attachment_url:
            note["attachment"] = [{"type": "Image", "url": attachment_url}]
        held.payload["object"] = note
        held.save(update_fields=["payload", "updated_at"])
        logger.info("announce: folded into held note %s", held.ap_id)
        return held

    content = "<br><br>".join(
        html for key, html in parts.items() if html and key in changed
    )
    if not content:
        return None
    return create_note(
        user,
        content,
        url=url,
        attachment_url=attachment_url,
        subject_key=subject_key,
        hold_seconds=_hold_seconds(),
    )


def create_note(
    user,
    content,
    url=None,
    attachment_url=None,
    subject_key="",
    hold_seconds=None,
):
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
        actor=actor,
        ap_id=activity_id,
        type="Create",
        payload=payload,
        subject_key=subject_key,
        # Measured from this first post about the subject and never extended,
        # so a member who keeps editing cannot defer delivery indefinitely.
        hold_until=(
            timezone.now() + timedelta(seconds=hold_seconds)
            if hold_seconds
            else None
        ),
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
