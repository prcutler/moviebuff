from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.conf import settings
from django.core.paginator import Paginator
from urllib.parse import urlparse
from .forms import RegisterForm
from movies.models import Watched, Watchlist, CustomWatchlist

PAGE_SIZE = 4


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
            "stars": "★" * int(w.rating) + "☆" * (5 - int(w.rating)),
        }
        for w in page_obj
    ]
    return {
        "movies": movies,
        "page": page_obj.number,
        "total_pages": paginator.num_pages,
    }


def home(request):
    recent_reviews = [
        {
            "movie": w.movie,
            "stars": "★" * int(w.rating) + "☆" * (5 - int(w.rating)),
        }
        for w in Watched.objects.select_related("movie")
        .exclude(rating__isnull=True)
        .order_by("-watched_date")[:5]
    ]
    return render(request, "users/home.html", {
        "home_movies": _build_home_movies_context(1),
        "recent_reviews": recent_reviews,
    })


def home_movies_page(request):
    if not request.headers.get("HX-Request"):
        return redirect("home")
    page_number = request.GET.get("page", 1)
    context = _build_home_movies_context(page_number)
    return render(request, "users/partials/home_movies.html", context)

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


@login_required
def dashboard(request):
    watched_qs = Watched.objects.filter(user=request.user).order_by('-watched_date')
    watchlist_qs = Watchlist.objects.filter(user=request.user).order_by('-added_date')
    custom_watchlists = CustomWatchlist.objects.filter(users=request.user).order_by('name')
    page_obj = Paginator(watched_qs, 8).get_page(1)

    return render(request, 'users/dashboard.html', {
        'page_obj': page_obj,
        'watched_rows': _annotate_stars(page_obj),
        'watchlist_page_obj': Paginator(watchlist_qs, 8).get_page(1),
        'custom_watchlists': custom_watchlists,
    })


@login_required
def dashboard_watched_page(request):
    if not request.headers.get('HX-Request'):
        return redirect('view_all_watched')
    watched_qs = Watched.objects.filter(user=request.user).order_by('-watched_date')
    page_obj = Paginator(watched_qs, 8).get_page(request.GET.get('page', 1))
    return render(request, 'users/partials/dashboard_watched.html', {
        'page_obj': page_obj,
        'watched_rows': _annotate_stars(page_obj),
    })


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
