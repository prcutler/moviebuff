from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse

from .forms import RegisterForm
from movies.models import Watched, Watchlist, CustomWatchlist


PUBLIC_KEY_PEM = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0e7eTwfhjWopDTAAOEbM\n"
    "eAPo4tgMGoYH9bInapvllkQXn5VsdXV2C/5cnEJaKKxKEpQHZaz1ztym3rV6LPsN\n"
    "7JdSaahcaZj/sULDxhuzAhqhYhKkuXAaB7GQafzuFE8Ppj+PHPsOfEsmfwxhZn3u\n"
    "NxI1e/1kGDJEyI/pddpVocRjvEHbkuoBONvzIeOSwDSiY5hIqcuBq7JbkWgIdnqb\n"
    "42nm2I9ATzqrm0tzX5JECGOlr63ZRVAvztGEFbJ5yV4p/vxXKDJ/FkB9Wb7TYX58\n"
    "Lweauhql8/IMyWZeTaMwyQRGPLhIIBG7RJQpXK+Bdyj1naHAbxPXNuk2q/3wjik7\n"
    "sQIDAQAB\n"
    "-----END PUBLIC KEY-----"
)

def home(request):
    return render(request, "users/home.html")

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
    return render(request, 'users/user_profile.html', {
        'profile_user': user,
        'watched_movies': watched_movies,
        'watchlist_movies': watchlist_movies
    })


def user_actor(request, username):
    user = get_object_or_404(User, username=username)
    if 'application/activity+json' in request.headers.get('Accept', ''):
        actor_url = request.build_absolute_uri(f'/users/{user.username}')
        data = {
            '@context': 'https://www.w3.org/ns/activitystreams',
            'id': actor_url,
            'type': 'Person',
            'preferredUsername': user.username,
            'inbox': f"{actor_url}/inbox",
            'outbox': f"{actor_url}/outbox",
            'followers': f"{actor_url}/followers",
            'publicKey': {
                'id': f"{actor_url}#main-key",
                'owner': actor_url,
                'publicKeyPem': PUBLIC_KEY_PEM,
            },
        }
        return JsonResponse(data, content_type='application/activity+json')
    return user_profile(request, username)

def logout_view(request):
    logout(request)
    return redirect('login')