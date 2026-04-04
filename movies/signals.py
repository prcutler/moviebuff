from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.html import escape
import uuid

from .models import Watchlist, Watched
from fedi.models import FediActivity, FediDelivery, FediFollower

PUBLIC = "https://www.w3.org/ns/activitystreams#Public"


def _create_note(user, content, url=None, attachment_url=None):
    if not settings.ACTIVITYPUB_ENABLED:
        return
    profile = getattr(user, "userprofile", None)
    if not profile or not profile.fedi_enabled:
        return
    actor = user.fediactor
    base = settings.ACTIVITYPUB_DOMAIN.rstrip("/")
    activity_id = f"{base}/activities/{uuid.uuid4()}"
    note_id = f"{activity_id}/note"
    note = {
        "id": note_id,
        "type": "Note",
        "attributedTo": actor.actor_id,
        "to": [PUBLIC],
        "cc": [actor.followers_url],
        "content": content,
    }
    if url:
        note["url"] = url
    if attachment_url:
        note["attachment"] = [{"type": "Image", "url": attachment_url}]

    payload = {
        "@context": "https://www.w3.org/ns/activitystreams",
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
    for follower in followers:
        FediDelivery.objects.create(activity=activity, follower=follower)


# @receiver(post_save, sender=Watchlist)
# def watchlist_added(sender, instance, created, **kwargs):
#     if not created:
#         return
#     movie = instance.movie
#     url = f"{settings.ACTIVITYPUB_DOMAIN.rstrip('/')}/movies/details/{movie.id}"
#     content = f"added {movie.title} to watchlist"
#     _create_note(
#         instance.user,
#         content,
#         url=url,
#         attachment_url=movie.tmdb_poster_path,
#     )


@receiver(pre_save, sender=Watched)
def store_previous_watched(sender, instance, **kwargs):
    if not instance.pk:
        instance._prev_rating = None
        instance._prev_review = ""
    else:
        try:
            prev = Watched.objects.get(pk=instance.pk)
            instance._prev_rating = prev.rating
            instance._prev_review = prev.review
        except Watched.DoesNotExist:
            instance._prev_rating = None
            instance._prev_review = ""


@receiver(post_save, sender=Watched)
def watched_events(sender, instance, created, **kwargs):
    movie = instance.movie
    url = f"{settings.ACTIVITYPUB_DOMAIN.rstrip('/')}/movies/details/{movie.id}"
    if created:
        date_str = instance.watched_date.date().isoformat()
        content = f"watched {movie.title} on {date_str}"
        _create_note(instance.user, content, url=url)
        return

    # rating updated
    if instance.rating is not None and instance.rating != getattr(instance, "_prev_rating", None):
        content = f"rated {movie.title} ⭐ {instance.rating}/5"
        _create_note(instance.user, content, url=url)
    # review created
    if instance.review and instance.review != getattr(instance, "_prev_review", ""):
        safe_review = escape(instance.review)
        content = f"{safe_review} <a href=\"{url}\">Read on MovieBuff</a>"
        _create_note(instance.user, content, url=url)
