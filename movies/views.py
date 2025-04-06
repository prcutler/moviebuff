from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from .models import Movie, Watched, Watchlist
from connectors.tmdb_connector import TMDbConnector
from django.conf import settings
from activitypub.utils import publish_activity
from activitypub.models import Actor
from .forms import WatchedForm

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
    is_watched = Watched.objects.filter(user=request.user, movie=movie).exists()
    is_in_watchlist = Watchlist.objects.filter(user=request.user, movie=movie).exists()

    watched_entry = Watched.objects.filter(user=request.user, movie=movie).first()

    return render(request, 'movies/movie_details.html', {
        'movie': movie,
        'is_watched': is_watched,
        'is_in_watchlist': is_in_watchlist,
        'watched_entry': watched_entry,
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
    Watchlist.objects.create(user=request.user, movie=movie)

    actor, created = Actor.objects.get_or_create(user=request.user)

    to_list = [follower.user_to.actor.get_absolute_url() for follower in request.user.followers.all()]
    publish_activity(actor, "Create", f"{request.user.username} a ajouté {movie.title} à sa liste de suivi.", to_list)

    return redirect('dashboard')

def remove_from_watched(request, movie_id):
    watched_entry = get_object_or_404(Watched, movie_id=movie_id, user=request.user)
    watched_entry.delete()
    return redirect('dashboard')

def remove_from_watchlist(request, movie_id):
    watchlist_entry = get_object_or_404(Watchlist, movie_id=movie_id, user=request.user)
    watchlist_entry.delete()
    return redirect('dashboard')

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