from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import RegisterForm
from movies.models import Watched, Watchlist

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
    watched_movies = Watched.objects.filter(user=request.user)
    watchlist_movies = Watchlist.objects.filter(user=request.user)
    return render(request, 'users/dashboard.html', {
        'watched_movies': watched_movies,
        'watchlist_movies': watchlist_movies
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