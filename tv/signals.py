"""Federating TV ratings and reviews, mirroring ``movies.signals``.

A shelf row is one table for both a show and a season, so the only extra
work here is naming the subject the post is about.
"""

import logging

from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.html import escape

from fedi.notes import create_note

from .models import TvShelf

logger = logging.getLogger(__name__)


def _subject_label(shelf):
    """How a show or season is named in a post."""
    if shelf.season_id is not None:
        season = shelf.season
        name = season.name or f"Season {season.season_number}"
        return f"{season.show.title} — {name}"
    return shelf.show.title


def _subject_url(shelf):
    base = settings.ACTIVITYPUB_DOMAIN.rstrip("/")
    if shelf.season_id is not None:
        season = shelf.season
        return f"{base}/tv/details/{season.show_id}/season/{season.season_number}/"
    return f"{base}/tv/details/{shelf.show_id}/"


def _poster(shelf):
    if shelf.season_id is not None:
        return shelf.season.tmdb_poster_path or shelf.season.show.tmdb_poster_path
    return shelf.show.tmdb_poster_path


@receiver(pre_save, sender=TvShelf)
def store_previous_shelf(sender, instance, **kwargs):
    if not instance.pk:
        instance._prev_rating = None
        instance._prev_review = ""
        return
    try:
        prev = TvShelf.objects.get(pk=instance.pk)
        instance._prev_rating = prev.rating
        instance._prev_review = prev.review
    except TvShelf.DoesNotExist:
        instance._prev_rating = None
        instance._prev_review = ""


@receiver(post_save, sender=TvShelf)
def shelf_events(sender, instance, created, **kwargs):
    """Post when a rating or review appears or changes.

    Shelving alone is deliberately quiet — adding something to a watchlist
    is not news, the same way ``movies`` keeps its watchlist signal off.
    """
    label = _subject_label(instance)
    url = _subject_url(instance)

    rating = instance.rating
    if rating is not None and rating != getattr(instance, "_prev_rating", None):
        content = f"rated {escape(label)} ⭐ {rating}/5"
        create_note(instance.user, content, url=url, attachment_url=_poster(instance) or None)

    review = instance.review
    if review and review != getattr(instance, "_prev_review", ""):
        safe_review = escape(review)
        content = f"{safe_review} <a href=\"{url}\">Read on MovieBuff</a>"
        create_note(instance.user, content, url=url)
