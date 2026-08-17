"""Turning TMDB payloads into catalogue rows.

Kept out of the views so a show can be refreshed from anywhere, and so the
awkward corners of the TMDB shape — a runtime that arrives as a list, a
poster that arrives as a bare path — are handled in exactly one place.
"""

import time

from django.conf import settings

from connectors.tmdb_connector import TMDbConnector
from .models import TvSeason, TvShow

POSTER_BASE = "https://image.tmdb.org/t/p/w600_and_h900_bestv2"

# How long a catalogue row is trusted before TMDB is asked again.
REFRESH_AFTER_SECONDS = 86400


def poster_url(poster_path):
    """Absolute poster URL from the bare path TMDB returns."""
    if not poster_path:
        return ""
    if poster_path.startswith("http"):
        return poster_path
    return f"{POSTER_BASE}{poster_path}"


def _first_runtime(payload):
    """TMDB reports episode runtime as a list, and often an empty one."""
    runtimes = payload.get("episode_run_time") or []
    return runtimes[0] if runtimes else None


def _connector():
    return TMDbConnector(api_key=settings.TMDB_API_KEY)


def show_needs_refresh(show):
    if show.last_updated is None:
        return True
    return (int(time.time()) - show.last_updated) > REFRESH_AFTER_SECONDS


def refresh_show(show, payload=None):
    """Update ``show`` from TMDB and sync its seasons. Returns the show."""
    if payload is None:
        payload = _connector().get_tv_details(show.tmdb_id)

    show.title = payload.get("name") or show.title
    show.overview = payload.get("overview") or show.overview
    show.first_air_date = payload.get("first_air_date") or show.first_air_date
    show.status = payload.get("status") or show.status
    show.episode_runtime = _first_runtime(payload) or show.episode_runtime
    show.original_language = payload.get("original_language") or show.original_language
    show.networks = [n["name"] for n in payload.get("networks", []) if n.get("name")]
    show.genres = [g["name"] for g in payload.get("genres", []) if g.get("name")]
    show.tmdb_poster_path = poster_url(payload.get("poster_path")) or show.tmdb_poster_path
    show.tmdb_vote_average = payload.get("vote_average", show.tmdb_vote_average)
    show.tmdb_vote_count = payload.get("vote_count", show.tmdb_vote_count)
    show.last_updated = int(time.time())
    show.save()

    _sync_seasons(show, payload.get("seasons", []))
    return show


def _sync_seasons(show, season_payloads):
    """Create or update the show's seasons.

    TMDB lists specials as season 0; they are kept, since a member may well
    want to shelve them, and skipping them would renumber nothing anyway.
    """
    for entry in season_payloads:
        number = entry.get("season_number")
        if number is None:
            continue
        TvSeason.objects.update_or_create(
            show=show,
            season_number=number,
            defaults={
                "name": entry.get("name") or "",
                "overview": entry.get("overview") or "",
                "air_date": entry.get("air_date") or None,
                "tmdb_poster_path": poster_url(entry.get("poster_path")),
                "episode_count": entry.get("episode_count") or 0,
            },
        )


def get_or_create_show(tmdb_id):
    """Fetch a show by TMDB id, creating and populating it if unseen."""
    show = TvShow.objects.filter(tmdb_id=tmdb_id).first()
    if show is None:
        show = TvShow.objects.create(tmdb_id=tmdb_id)
        return refresh_show(show)
    if show_needs_refresh(show):
        refresh_show(show)
    return show
