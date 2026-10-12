"""Federating TV ratings and reviews, mirroring ``movies.signals``.

A shelf row is one table for both a show and a season, so the only extra
work here is naming the subject the post is about.
"""

import logging

from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.html import escape

from fedi.notes import announce

from .models import TvShelf

logger = logging.getLogger(__name__)


def _subject_url(shelf):
    base = settings.ACTIVITYPUB_DOMAIN.rstrip("/")
    return f"{base}{shelf.get_absolute_url()}"


@receiver(pre_save, sender=TvShelf)
def store_previous_shelf(sender, instance, **kwargs):
    if not instance.pk:
        instance._prev_rating = None
        instance._prev_review = ""
        instance._prev_rewatch = False
        return
    try:
        prev = TvShelf.objects.get(pk=instance.pk)
        instance._prev_rating = prev.rating
        instance._prev_review = prev.review
        instance._prev_rewatch = prev.rewatch
    except TvShelf.DoesNotExist:
        instance._prev_rating = None
        instance._prev_review = ""
        instance._prev_rewatch = False


@receiver(post_save, sender=TvShelf)
def shelf_events(sender, instance, created, **kwargs):
    """Announce when a rating or review appears or changes.

    Shelving alone is deliberately quiet — adding something to a watchlist
    is not news, the same way ``movies`` keeps its watchlist signal off.
    """
    changed = set()
    if instance.rating != getattr(instance, "_prev_rating", None):
        changed.add("rating")
    if instance.review != getattr(instance, "_prev_review", ""):
        changed.add("review")
    # Not a part of its own: it only rewords a rating that is still held.
    if instance.rewatch != getattr(instance, "_prev_rewatch", False):
        changed.add("rewatch")
    if not changed:
        return

    url = _subject_url(instance)
    verb = "re-watched" if instance.rewatch else "watched"
    parts = {
        "rating": (
            f"I just {verb} and rated {escape(instance.display_title)} ⭐ {instance.rating}/5"
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
        subject_key=f"tvshelf:{instance.pk}",
        url=url,
        attachment_url=instance.poster or None,
    )
