from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.html import escape
import logging

from .models import Watchlist, Watched
from fedi.notes import announce

logger = logging.getLogger(__name__)


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
    """Announce when a rating or review appears or changes.

    Deliberately does not skip newly created rows: the "Add to Watched" form
    saves the date, rating and review in one step, so a rating that arrives
    with the row is a rating like any other. Logging a viewing with neither
    stays quiet, because there is then nothing to say.
    """
    changed = set()
    if instance.rating != getattr(instance, "_prev_rating", None):
        changed.add("rating")
    if instance.review != getattr(instance, "_prev_review", ""):
        changed.add("review")
    if not changed:
        return

    movie = instance.movie
    url = f"{settings.ACTIVITYPUB_DOMAIN.rstrip('/')}/movies/details/{movie.id}"
    parts = {
        "rating": (
            f"rated {movie.title} ⭐ {instance.rating}/5"
            if instance.rating is not None
            else ""
        ),
        "review": (
            f'{escape(instance.review)} <a href="{url}">Read on MovieBuff</a>'
            if instance.review
            else ""
        ),
    }

    announce(
        instance.user,
        parts,
        changed,
        subject_key=f"movie:{movie.id}",
        url=url,
        attachment_url=movie.tmdb_poster_path or None,
    )
