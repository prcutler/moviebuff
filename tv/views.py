from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import TvSeason, TvShelf, TvShow
from .services import get_or_create_show, refresh_show, show_needs_refresh


def search_tv(request):
    """Kept so old links still work; TV search now lives in the one search."""
    params = urlencode({"q": request.GET.get("q", ""), "kind": "tv"})
    return redirect(f"{reverse('search')}?{params}")


def handle_tmdb_redirect(request, tmdb_id):
    """Land on a show's page from a TMDB search result."""
    show = get_or_create_show(tmdb_id)
    return redirect("tv_show_details", show_id=show.id)


def _shelf_for(user, *, show=None, season=None):
    if not user.is_authenticated:
        return None
    if season is not None:
        return TvShelf.objects.filter(user=user, season=season).first()
    return TvShelf.objects.filter(user=user, show=show).first()


def tv_show_details(request, show_id):
    show = get_object_or_404(TvShow, id=show_id)
    if show_needs_refresh(show):
        refresh_show(show)

    average_rating = TvShelf.objects.filter(
        show=show, rating__isnull=False
    ).aggregate(Avg("rating"))["rating__avg"]
    other_reviews = (
        TvShelf.objects.filter(show=show)
        .exclude(review__exact="")
        .order_by("-updated_at")
    )

    user_shelf = _shelf_for(request.user, show=show)

    # Hang each season's standing off the season itself, so the template can
    # read it directly instead of searching a dict per row.
    seasons = list(show.seasons.all())
    if request.user.is_authenticated:
        by_season = {
            entry.season_id: entry
            for entry in TvShelf.objects.filter(user=request.user, season__show=show)
        }
        for season in seasons:
            season.user_shelf = by_season.get(season.id)

    return render(
        request,
        "tv/show_details.html",
        {
            "show": show,
            "seasons": seasons,
            "user_shelf": user_shelf,
            "user_rating": int(user_shelf.rating)
            if user_shelf and user_shelf.rating is not None
            else 0,
            "average_rating": average_rating,
            "total_reviews": other_reviews.count(),
            "other_reviews": other_reviews,
            "state_choices": TvShelf.STATE_CHOICES,
        },
    )


def tv_season_details(request, show_id, season_number):
    season = get_object_or_404(
        TvSeason.objects.select_related("show"),
        show_id=show_id,
        season_number=season_number,
    )
    user_shelf = _shelf_for(request.user, season=season)
    other_reviews = (
        TvShelf.objects.filter(season=season)
        .exclude(review__exact="")
        .order_by("-updated_at")
    )
    average_rating = TvShelf.objects.filter(
        season=season, rating__isnull=False
    ).aggregate(Avg("rating"))["rating__avg"]

    return render(
        request,
        "tv/season_details.html",
        {
            "season": season,
            "show": season.show,
            "user_shelf": user_shelf,
            "user_rating": int(user_shelf.rating)
            if user_shelf and user_shelf.rating is not None
            else 0,
            "average_rating": average_rating,
            "total_reviews": other_reviews.count(),
            "other_reviews": other_reviews,
            "state_choices": TvShelf.STATE_CHOICES,
        },
    )


def _resolve_subject(show_id, season_number):
    """Return the kwargs naming whichever subject the request is about."""
    if season_number is None:
        return {"show": get_object_or_404(TvShow, id=show_id)}
    season = get_object_or_404(
        TvSeason, show_id=show_id, season_number=season_number
    )
    return {"season": season}


@login_required
@require_POST
def set_state(request, show_id, season_number=None):
    """Move a show or season to a shelf state, or off the shelf entirely."""
    state = request.POST.get("state", "")
    subject = _resolve_subject(show_id, season_number)

    if state == "":
        TvShelf.objects.filter(user=request.user, **subject).delete()
        return _redirect_to_subject(show_id, season_number)

    valid = {choice for choice, _ in TvShelf.STATE_CHOICES}
    if state not in valid:
        return JsonResponse(
            {"success": False, "message": "Unknown state"}, status=400
        )

    shelf, _ = TvShelf.objects.get_or_create(
        user=request.user, defaults={"state": state}, **subject
    )
    shelf.state = state
    if state == TvShelf.WATCHED and shelf.watched_date is None:
        shelf.watched_date = timezone.now()
    shelf.save()
    return _redirect_to_subject(show_id, season_number)


@login_required
@require_POST
def update_rating(request, show_id, season_number=None):
    try:
        rating = float(request.POST.get("rating", ""))
    except ValueError:
        return JsonResponse(
            {"success": False, "message": "Invalid rating"}, status=400
        )
    if not 0.0 <= rating <= 5.0:
        return JsonResponse(
            {"success": False, "message": "Rating must be between 0 and 5"},
            status=400,
        )

    subject = _resolve_subject(show_id, season_number)
    # Rating something implies you watched it, which is the state a bare
    # rating should leave behind when nothing was on the shelf yet.
    shelf, _ = TvShelf.objects.get_or_create(
        user=request.user, defaults={"state": TvShelf.WATCHED}, **subject
    )
    shelf.rating = rating
    if shelf.state == TvShelf.WATCHLIST:
        shelf.state = TvShelf.WATCHED
    if shelf.state == TvShelf.WATCHED and shelf.watched_date is None:
        shelf.watched_date = timezone.now()
    shelf.save()
    return _redirect_to_subject(show_id, season_number)


@login_required
@require_POST
def submit_review(request, show_id, season_number=None):
    review = (request.POST.get("review") or "").strip()
    subject = _resolve_subject(show_id, season_number)
    shelf, _ = TvShelf.objects.get_or_create(
        user=request.user, defaults={"state": TvShelf.WATCHED}, **subject
    )
    shelf.review = review[:300]
    shelf.save()
    return _redirect_to_subject(show_id, season_number)


def _redirect_to_subject(show_id, season_number):
    if season_number is None:
        return redirect("tv_show_details", show_id=show_id)
    return redirect(
        "tv_season_details", show_id=show_id, season_number=season_number
    )


@login_required
def view_all_shelf(request, state):
    """List everything the member has put in one shelf state."""
    valid = {choice for choice, _ in TvShelf.STATE_CHOICES}
    if state not in valid:
        return redirect("search")

    entries = (
        TvShelf.objects.filter(user=request.user, state=state)
        .select_related("show", "season", "season__show")
        .order_by("-updated_at")
    )
    paginator = Paginator(entries, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    label = dict(TvShelf.STATE_CHOICES)[state]
    return render(
        request,
        "tv/view_all_shelf.html",
        {"page_obj": page_obj, "state": state, "state_label": label},
    )
