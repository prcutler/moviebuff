from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.html import escape
import logging

from .models import Watchlist, Watched
from fedi.notes import create_note as _create_note

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
    movie = instance.movie
    url = f"{settings.ACTIVITYPUB_DOMAIN.rstrip('/')}/movies/details/{movie.id}"
    if created:
        return

    # rating updated
    if instance.rating is not None and instance.rating != getattr(instance, "_prev_rating", None):
        content = f"rated {movie.title} ⭐ {instance.rating}/5"
        _create_note(instance.user, content, url=url, attachment_url=movie.tmdb_poster_path or None)
    # review created
    if instance.review and instance.review != getattr(instance, "_prev_review", ""):
        safe_review = escape(instance.review)
        content = f"{safe_review} <a href=\"{url}\">Read on MovieBuff</a>"
        _create_note(instance.user, content, url=url)
