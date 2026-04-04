from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.conf import settings
from urllib.parse import urlparse
from .forms import RegisterForm
from movies.models import Watched, Watchlist, CustomWatchlist

def home(request):
    random_movies = (
        Watched.objects.select_related("movie")
        .exclude(movie__tmdb_poster_path="")
        .order_by("?")[:4]
    )
    return render(request, "users/home.html", {"random_movies": random_movies})

def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = RegisterForm()
    return render(request, "users/register.html", {"form": form})

@login_required
def dashboard(request):
    watched_movies = Watched.objects.filter(user=request.user).order_by('-watched_date')
    watchlist_movies = Watchlist.objects.filter(user=request.user).order_by('-added_date')
    custom_watchlists = CustomWatchlist.objects.filter(users=request.user).order_by('name')

    return render(request, 'users/dashboard.html', {
        'watched_movies': watched_movies,
        'watchlist_movies': watchlist_movies,
        'custom_watchlists': custom_watchlists,
    })

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
