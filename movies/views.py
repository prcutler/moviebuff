import time
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from .models import Movie, Watched, Watchlist, CustomWatchlist, CustomWatchlistItem
from connectors.tmdb_connector import TMDbConnector
from django.conf import settings
from activitypub.utils import publish_activity
from activitypub.models import Actor
from .forms import WatchedForm, WatchlistForm

def search_movies(request):
    query = request.GET.get('q')
    if query:
        tmdb_connector = TMDbConnector(api_key=settings.TMDB_API_KEY)
        results = tmdb_connector.search_movie(query)
        paginator = Paginator(results, 10) 
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        return render(request, 'movies/search_results.html', {'page_obj': page_obj, 'query': query})
    return render(request, 'movies/search_results.html')

def movie_details(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)

    # Check if any data is missing or outdated
    current_time = int(time.time())
    data_missing = (
        not movie.overview or
        not movie.release_date or
        not movie.original_language or
        not movie.budget or
        not movie.runtime or
        not movie.tmdb_vote_average or
        not movie.tmdb_vote_count or
        not movie.imdb_id or
        not movie.tmdb_poster_path or
        (current_time - movie.last_updated > 86400)  # Update if older than 24 hours
    )

    if data_missing:
        tmdb_connector = TMDbConnector(api_key=settings.TMDB_API_KEY)
        movie_data = tmdb_connector.get_movie_details(movie.tmdb_id)

        # Update movie details
        movie.title = movie_data.get('title', movie.title)
        movie.overview = movie_data.get('overview', movie.overview)
        movie.release_date = movie_data.get('release_date', movie.release_date)
        movie.original_language = movie_data.get('original_language', movie.original_language)
        movie.budget = movie_data.get('budget', movie.budget)
        movie.runtime = movie_data.get('runtime', movie.runtime)
        movie.tmdb_vote_average = movie_data.get('vote_average', movie.tmdb_vote_average)
        movie.tmdb_vote_count = movie_data.get('vote_count', movie.tmdb_vote_count)
        movie.imdb_id = movie_data.get('imdb_id', movie.imdb_id)
        movie.tmdb_poster_path = "https://image.tmdb.org/t/p/w600_and_h900_bestv2" + movie_data.get('poster_path', movie.tmdb_poster_path.split("/")[-1])
        movie.last_updated = current_time
        movie.save()

    is_watched = Watched.objects.filter(user=request.user, movie=movie).exists()
    is_in_watchlist = Watchlist.objects.filter(user=request.user, movie=movie).exists()
    watched_entry = Watched.objects.filter(user=request.user, movie=movie).first()

    # Get custom watchlists that contain the movie
    custom_watchlists = CustomWatchlist.objects.filter(items__movie=movie, users=request.user).distinct()

    return render(request, 'movies/movie_details.html', {
        'movie': movie,
        'is_watched': is_watched,
        'is_in_watchlist': is_in_watchlist,
        'watched_entry': watched_entry,
        'custom_watchlists': custom_watchlists,
    })

def add_to_watched(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    if request.method == 'POST':
        form = WatchedForm(request.POST)
        if form.is_valid():
            watched = form.save(commit=False)
            watched.user = request.user
            watched.movie = movie
            watched.save()

            # Publish activity
            actor, created = Actor.objects.get_or_create(user=request.user)
            to_list = [follower.user_to.actor.get_absolute_url() for follower in request.user.followers.all()]
            publish_activity(actor, "Create", f"{request.user.username} a regardé {movie.title}.", to_list)

            return redirect('dashboard')
    else:
        form = WatchedForm()

    return render(request, 'movies/add_to_watched.html', {'form': form, 'movie': movie})

def add_to_watchlist(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    if request.method == 'POST':
        form = WatchlistForm(request.POST, user=request.user)
        if form.is_valid():
            watchlist_choice = form.cleaned_data['watchlist']
            if watchlist_choice == 'default':
                Watchlist.objects.create(user=request.user, movie=movie)
            elif watchlist_choice == 'new':
                new_watchlist = CustomWatchlist.objects.create(
                    name=form.cleaned_data['new_watchlist_name'],
                    description=form.cleaned_data['new_watchlist_description'],
                    created_by=request.user
                )
                new_watchlist.users.add(request.user)
                CustomWatchlistItem.objects.create(watchlist=new_watchlist, movie=movie, added_by=request.user)
            else:
                custom_watchlist = CustomWatchlist.objects.get(id=watchlist_choice)
                CustomWatchlistItem.objects.create(watchlist=custom_watchlist, movie=movie, added_by=request.user)
            return redirect('dashboard')
    else:
        form = WatchlistForm(user=request.user)

    return render(request, 'movies/add_to_watchlist.html', {'form': form, 'movie': movie})

def remove_from_watched(request, movie_id):
    watched_entry = get_object_or_404(Watched, movie_id=movie_id, user=request.user)
    watched_entry.delete()
    return redirect('dashboard')

def remove_from_watchlist(request, movie_id):
    watchlist_entry = get_object_or_404(Watchlist, movie_id=movie_id, user=request.user)
    watchlist_entry.delete()
    return redirect('dashboard')

def remove_from_custom_watchlist(request, movie_id, watchlist_id):
    movie = get_object_or_404(Movie, id=movie_id)
    custom_watchlist_item = get_object_or_404(CustomWatchlistItem, watchlist_id=watchlist_id, movie=movie)
    custom_watchlist_item.delete()
    return redirect('movie_details', movie_id=movie.id)

def delete_custom_watchlist(request, watchlist_id):
    custom_watchlist = get_object_or_404(CustomWatchlist, id=watchlist_id, users=request.user)
    custom_watchlist.delete()
    return redirect('dashboard')

def view_all_watched(request):
    watched_movies = Watched.objects.filter(user=request.user).order_by('-watched_date')
    return render(request, 'movies/view_all_watched.html', {'watched_movies': watched_movies})

def view_all_watchlist(request):
    watchlist_movies = Watchlist.objects.filter(user=request.user).order_by('-added_date')
    return render(request, 'movies/view_all_watchlist.html', {'watchlist_movies': watchlist_movies})

def view_custom_watchlist(request, watchlist_id):
    custom_watchlist = get_object_or_404(CustomWatchlist, id=watchlist_id, users=request.user)
    custom_watchlist_items = custom_watchlist.items.all().order_by('-added_date')
    return render(request, 'movies/view_custom_watchlist.html', {'custom_watchlist': custom_watchlist, 'custom_watchlist_items': custom_watchlist_items})

def handle_tmdb_redirect(request, tmdb_id):
    movie = Movie.objects.filter(tmdb_id=tmdb_id).first()
    if movie:
        return redirect('movie_details', movie_id=movie.id)
    else:
        tmdb_connector = TMDbConnector(api_key=settings.TMDB_API_KEY)
        movie_data = tmdb_connector.get_movie_details(tmdb_id)
        movie = Movie.objects.create(
            tmdb_id=movie_data['id'],
            title=movie_data['title'],
            overview=movie_data['overview'],
            release_date=movie_data['release_date'],
            tmdb_poster_path="https://image.tmdb.org/t/p/w600_and_h900_bestv2" + movie_data['poster_path']
        )
        return redirect('movie_details', movie_id=movie.id)