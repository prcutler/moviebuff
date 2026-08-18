from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.urls import reverse
from urllib.parse import urlparse
from .forms import RegisterForm
from movies.models import Watched, Watchlist, CustomWatchlist
from tv.models import TvShelf

PAGE_SIZE = 4

# How many entries the "Recent Ratings" list shows.
RECENT_RATINGS = 5

# Dashboard grids are four across, so these are whole rows.
DASHBOARD_PAGE_SIZE = 8
# Watched Movies gives up its second row to the TV section below it.
DASHBOARD_WATCHED_PAGE_SIZE = 4
DASHBOARD_TV_PAGE_SIZE = 4


def _stars(rating):
    """Five-star string for a 0–5 rating, empty when unrated."""
    if rating is None:
        return ""
    filled = int(rating)
    return "★" * filled + "☆" * (5 - filled)


def _build_home_movies_context(page_number):
    qs = (
        Watched.objects.select_related("movie")
        .exclude(movie__tmdb_poster_path="")
        .exclude(rating__isnull=True)
        .order_by("-watched_date")
    )
    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    movies = [
        {
            "movie": w.movie,
            "stars": _stars(w.rating),
        }
        for w in page_obj
    ]
    return {
        "movies": movies,
        "page": page_obj.number,
        "total_pages": paginator.num_pages,
    }


def _watched_tv_queryset(user=None):
    """Finished shows and seasons, newest first, optionally for one member.

    Ordered by when it was finished, falling back to when the row last
    changed — ``watched_date`` is only stamped by the shelf views, so a row
    created another way (admin, a fixture) would otherwise sort last.
    """
    qs = TvShelf.objects.filter(state=TvShelf.WATCHED).select_related(
        "show", "season", "season__show"
    )
    if user is not None:
        qs = qs.filter(user=user)
    return (
        # Matching the movie grids, which only draw entries that have art.
        qs.exclude(Q(season__isnull=True) & Q(show__tmdb_poster_path=""))
        .exclude(
            Q(season__isnull=False)
            & Q(season__tmdb_poster_path="")
            & Q(season__show__tmdb_poster_path="")
        )
        .annotate(finished_at=Coalesce("watched_date", "updated_at"))
        .order_by("-finished_at")
    )


def _build_home_tv_context(page_number):
    """The most recently finished shows and seasons across everyone."""
    paginator = Paginator(_watched_tv_queryset(), PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    tv = [
        {
            "title": entry.display_title,
            "poster": entry.poster,
            "url": entry.get_absolute_url(),
            # Watched without a rating is normal here, unlike the movie grid.
            "stars": _stars(entry.rating),
        }
        for entry in page_obj
    ]
    return {
        "tv": tv,
        "page": page_obj.number,
        "total_pages": paginator.num_pages,
    }


def _build_recent_ratings(limit=RECENT_RATINGS):
    """The newest ratings across both catalogues, movies and TV interleaved.

    The two sources have different shapes and different date columns, so they
    are merged in Python rather than in SQL. Taking ``limit`` from each first
    is enough to be correct: any entry in the overall newest ``limit`` must
    also be within the newest ``limit`` of the source it came from.
    """
    movies = [
        {
            "title": w.movie.title,
            "url": reverse("movie_details", args=[w.movie_id]),
            "stars": _stars(w.rating),
            "when": w.watched_date,
        }
        for w in Watched.objects.select_related("movie")
        .exclude(rating__isnull=True)
        .order_by("-watched_date")[:limit]
    ]
    # Any rated row counts, not only finished ones — a series rated partway
    # through is still a rating, and this list is about ratings.
    tv = [
        {
            "title": entry.display_title,
            "url": entry.get_absolute_url(),
            "stars": _stars(entry.rating),
            "when": entry.finished_at,
        }
        for entry in TvShelf.objects.select_related(
            "show", "season", "season__show"
        )
        .exclude(rating__isnull=True)
        .annotate(finished_at=Coalesce("watched_date", "updated_at"))
        .order_by("-finished_at")[:limit]
    ]

    combined = movies + tv
    combined.sort(key=lambda entry: entry["when"], reverse=True)
    return combined[:limit]


def home(request):
    recent_reviews = _build_recent_ratings()
    return render(request, "users/home.html", {
        "home_movies": _build_home_movies_context(1),
        "home_tv": _build_home_tv_context(1),
        "recent_reviews": recent_reviews,
    })


def home_movies_page(request):
    if not request.headers.get("HX-Request"):
        return redirect("home")
    page_number = request.GET.get("page", 1)
    context = _build_home_movies_context(page_number)
    return render(request, "users/partials/home_movies.html", context)


def home_tv_page(request):
    if not request.headers.get("HX-Request"):
        return redirect("home")
    page_number = request.GET.get("page", 1)
    context = _build_home_tv_context(page_number)
    return render(request, "users/partials/home_tv.html", context)

def register(request):
    if not settings.REGISTRATION_ENABLED:
        raise Http404
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = RegisterForm()
    return render(request, "users/register.html", {"form": form})

def _annotate_stars(page_obj):
    """Return list of (watched, stars_string) tuples for a page."""
    result = []
    for w in page_obj:
        stars = "★" * int(w.rating) + "☆" * (5 - int(w.rating)) if w.rating is not None else ""
        result.append((w, stars))
    return result


def _build_dashboard_tv_context(user, page_number):
    """One row of the member's own most recently finished shows and seasons."""
    paginator = Paginator(_watched_tv_queryset(user), DASHBOARD_TV_PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    return {
        'tv_page_obj': page_obj,
        'tv_rows': [
            {
                'title': entry.display_title,
                'poster': entry.poster,
                'url': entry.get_absolute_url(),
                'finished': entry.finished_at,
                'stars': _stars(entry.rating),
            }
            for entry in page_obj
        ],
    }


@login_required
def dashboard(request):
    watched_qs = Watched.objects.filter(user=request.user).order_by('-watched_date')
    watchlist_qs = Watchlist.objects.filter(user=request.user).order_by('-added_date')
    custom_watchlists = CustomWatchlist.objects.filter(users=request.user).order_by('name')
    page_obj = Paginator(watched_qs, DASHBOARD_WATCHED_PAGE_SIZE).get_page(1)

    return render(request, 'users/dashboard.html', {
        'page_obj': page_obj,
        'watched_rows': _annotate_stars(page_obj),
        'watchlist_page_obj': Paginator(watchlist_qs, DASHBOARD_PAGE_SIZE).get_page(1),
        'custom_watchlists': custom_watchlists,
        **_build_dashboard_tv_context(request.user, 1),
    })


@login_required
def dashboard_watched_page(request):
    if not request.headers.get('HX-Request'):
        return redirect('view_all_watched')
    watched_qs = Watched.objects.filter(user=request.user).order_by('-watched_date')
    page_obj = Paginator(watched_qs, DASHBOARD_WATCHED_PAGE_SIZE).get_page(
        request.GET.get('page', 1)
    )
    return render(request, 'users/partials/dashboard_watched.html', {
        'page_obj': page_obj,
        'watched_rows': _annotate_stars(page_obj),
    })


@login_required
def dashboard_tv_page(request):
    if not request.headers.get('HX-Request'):
        return redirect('tv_view_all_shelf', state=TvShelf.WATCHED)
    context = _build_dashboard_tv_context(request.user, request.GET.get('page', 1))
    return render(request, 'users/partials/dashboard_tv.html', context)


@login_required
def dashboard_watchlist_page(request):
    if not request.headers.get('HX-Request'):
        return redirect('view_all_watchlist')
    watchlist_qs = Watchlist.objects.filter(user=request.user).order_by('-added_date')
    page_obj = Paginator(watchlist_qs, 8).get_page(request.GET.get('page', 1))
    return render(request, 'users/partials/dashboard_watchlist.html', {'page_obj': page_obj})

def user_profile(request, username):
    user = get_object_or_404(User, username=username)
    watched_movies = Watched.objects.filter(user=user)
    watchlist_movies = Watchlist.objects.filter(user=user)

    if request.user == user and request.method == "POST":
        profile = user.userprofile
        profile.fedi_enabled = bool(request.POST.get("fedi_enabled"))
        profile.fedi_discoverable = bool(request.POST.get("fedi_discoverable"))
        profile.save()
        messages.success(request, "Fediverse settings updated")
        return redirect("user_profile", username=user.username)

    profile = user.userprofile
    domain = urlparse(settings.ACTIVITYPUB_DOMAIN or "").hostname or request.get_host()
    remote_handle = f"@{user.username}@{domain}"
    return render(
        request,
        'users/user_profile.html',
        {
            'profile_user': user,
            'watched_movies': watched_movies,
            'watchlist_movies': watchlist_movies,
            'profile': profile,
            'remote_handle': remote_handle,
        },
    )

def logout_view(request):
    logout(request)
    return redirect('login')
