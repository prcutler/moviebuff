"""One search across the whole catalogue: movies and shows together.

Asks TMDB once over its ``/search/multi`` endpoint, so a half-remembered
title turns up whether it was a film or a series. A movie and a show name
the same things differently — ``title`` against ``name``, ``release_date``
against ``first_air_date`` — so each hit is normalised into one shape here,
and everything downstream reads only that.
"""

from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import render

from connectors.tmdb_connector import TMDbConnector

POSTER_THUMB_BASE = "https://image.tmdb.org/t/p/w342"

# TMDB tags every multi-search hit with what it found. It also returns
# people, which this catalogue has nowhere to put, so only these are kept.
KEPT_KINDS = ("movie", "tv")

RESULTS_PER_PAGE = 12


def _thumb(poster_path):
    if not poster_path:
        return ""
    return f"{POSTER_THUMB_BASE}{poster_path}"


def _card(result):
    """Normalise one TMDB hit into the single shape the card template reads."""
    kind = result.get("media_type")
    if kind == "tv":
        title = result.get("name") or ""
        date = result.get("first_air_date") or ""
    else:
        title = result.get("title") or ""
        date = result.get("release_date") or ""
    return {
        "kind": kind,
        "tmdb_id": result.get("id"),
        "title": title,
        "year": date[:4],
        "overview": result.get("overview") or "",
        "poster_url": _thumb(result.get("poster_path")),
        "popularity": result.get("popularity") or 0,
    }


def _search_results(connector, query, kind):
    """Fetch results for ``query``, narrowed to ``kind`` when one is given.

    A narrowed search asks that kind's own endpoint, which returns a fuller
    list of it than the blended one does. Those endpoints don't tag hits with
    a media_type, so it is supplied here.
    """
    if kind == "movie":
        return [dict(r, media_type="movie") for r in connector.search_movie(query)]
    if kind == "tv":
        return [dict(r, media_type="tv") for r in connector.search_tv(query)]
    return connector.search_multi(query)


def search(request):
    query = (request.GET.get("q") or "").strip()
    kind = request.GET.get("kind") or ""
    if kind not in KEPT_KINDS:
        kind = ""

    if not query:
        return render(request, "moviebuff/search_results.html", {"kind": kind})

    connector = TMDbConnector(api_key=settings.TMDB_API_KEY)
    raw = _search_results(connector, query, kind)
    cards = [_card(r) for r in raw if r.get("media_type") in KEPT_KINDS]

    paginator = Paginator(cards, RESULTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "moviebuff/search_results.html",
        {
            "page_obj": page_obj,
            "query": query,
            "kind": kind,
            "total": len(cards),
        },
    )
