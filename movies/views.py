import time
import uuid
from django.db.models import Avg
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils.html import escape
from .models import Movie, Watched, Watchlist, CustomWatchlist, CustomWatchlistItem
from connectors.tmdb_connector import TMDbConnector
from django.conf import settings
from .forms import WatchedForm, WatchlistForm

def search_movies(request):
    query = request.GET.get('q')
    if query:
        tmdb_connector = TMDbConnector(api_key=settings.TMDB_API_KEY)
        results = tmdb_connector.search_movie(query)
        paginator = Paginator(results, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'movies/components/search_result_cards.html',
                {'page_obj': page_obj},
                request=request,
            )
            next_url = None
            if page_obj.has_next():
                next_url = (
                    f"{request.path}?page={page_obj.next_page_number}&q={escape(query)}"
                )
            return JsonResponse({'html': html, 'next_url': next_url})

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
    user_rating = int(watched_entry.rating) if watched_entry and watched_entry.rating is not None else 0

    # Get custom watchlists that contain the movie
    custom_watchlists = CustomWatchlist.objects.filter(items__movie=movie, users=request.user).distinct()

    # Calculate user stats
    total_reviews = Watched.objects.filter(movie=movie, review__isnull=False).count()
    average_rating = Watched.objects.filter(movie=movie, rating__isnull=False).aggregate(Avg('rating'))['rating__avg']
    other_reviews = Watched.objects.filter(movie=movie, review__isnull=False).exclude(review__exact='').order_by('-watched_date')

    return render(request, 'movies/movie_details.html', {
        'movie': movie,
        'is_watched': is_watched,
        'is_in_watchlist': is_in_watchlist,
        'watched_entry': watched_entry,
        'user_rating': user_rating,
        'custom_watchlists': custom_watchlists,
        'total_reviews': total_reviews,
        'average_rating': average_rating,
        'other_reviews': other_reviews,
    })


@login_required
@require_POST
def toggle_watchlist(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    entry = Watchlist.objects.filter(user=request.user, movie=movie).first()
    if entry:
        entry.delete()
        return JsonResponse({
            'success': True,
            'message': 'Removed from watchlist',
            'new_label': 'Add to Watchlist',
        })
    else:
        Watchlist.objects.create(user=request.user, movie=movie)
        return JsonResponse({
            'success': True,
            'message': 'Added to watchlist',
            'new_label': 'Remove from Watchlist',
        })


@login_required
@require_POST
def toggle_watched(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    entry = Watched.objects.filter(user=request.user, movie=movie).first()
    if entry:
        entry.delete()
        return JsonResponse({
            'success': True,
            'message': 'Removed from watched',
            'new_label': 'Add to Watched',
        })
    else:
        Watched.objects.create(user=request.user, movie=movie, watched_date=timezone.now())
        return JsonResponse({
            'success': True,
            'message': 'Added to watched',
            'new_label': 'Remove from Watched',
        })

def add_to_watched(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    existing = Watched.objects.filter(user=request.user, movie=movie).first()
    if request.method == 'POST':
        form = WatchedForm(request.POST)
        if form.is_valid():
            is_rewatch = form.cleaned_data.get('is_rewatch')
            instance = form.save(commit=False)
            if existing:
                if is_rewatch:
                    existing.rewatch_count += 1
                existing.watched_date = instance.watched_date
                existing.rating = form.cleaned_data.get('rating')
                existing.review = form.cleaned_data.get('review')
                existing.save()
            else:
                instance.user = request.user
                instance.movie = movie
                instance.save()

            return redirect('dashboard')
    else:
        form = WatchedForm()

    return render(request, 'movies/add_to_watched.html', {'form': form, 'movie': movie, 'existing': existing})

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
    paginator = Paginator(watched_movies, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string(
            'movies/components/movie_card_list.html',
            {'page_obj': page_obj},
            request=request,
        )
        next_url = None
        if page_obj.has_next():
            next_url = f"{request.path}?page={page_obj.next_page_number}"
        return JsonResponse({'html': html, 'next_url': next_url})

    return render(request, 'movies/view_all_watched.html', {'page_obj': page_obj})

def view_all_watchlist(request):
    watchlist_movies = Watchlist.objects.filter(user=request.user).order_by('-added_date')
    paginator = Paginator(watchlist_movies, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string(
            'movies/components/movie_card_list.html',
            {'page_obj': page_obj},
            request=request,
        )
        next_url = None
        if page_obj.has_next():
            next_url = f"{request.path}?page={page_obj.next_page_number}"
        return JsonResponse({'html': html, 'next_url': next_url})

    return render(request, 'movies/view_all_watchlist.html', {'page_obj': page_obj})

def view_custom_watchlist(request, watchlist_id):
    custom_watchlist = get_object_or_404(CustomWatchlist, id=watchlist_id, users=request.user)
    custom_watchlist_items = custom_watchlist.items.all().order_by('-added_date')
    paginator = Paginator(custom_watchlist_items, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string(
            'movies/components/movie_card_list.html',
            {'page_obj': page_obj},
            request=request,
        )
        next_url = None
        if page_obj.has_next():
            next_url = f"{request.path}?page={page_obj.next_page_number}"
        return JsonResponse({'html': html, 'next_url': next_url})

    return render(
        request,
        'movies/view_custom_watchlist.html',
        {'custom_watchlist': custom_watchlist, 'page_obj': page_obj},
    )

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


@login_required
@require_POST
def update_rating(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    try:
        rating = float(request.POST.get('rating'))
    except (TypeError, ValueError):
        return JsonResponse({
            'success': False,
            'message': 'Invalid rating'
        }, status=400)

    watched, _ = Watched.objects.get_or_create(
        user=request.user,
        movie=movie,
        defaults={'watched_date': timezone.now()}
    )
    watched.rating = rating
    watched.save()

    return JsonResponse({
        'success': True,
        'message': 'Rating saved',
        'rating': rating
    })


@login_required
@require_POST
def submit_review(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    review_text = request.POST.get('review', '').strip()

    if not review_text:
        return JsonResponse({
            'success': False,
            'message': 'Review cannot be empty'
        }, status=400)

    if len(review_text) > 300:
        return JsonResponse({
            'success': False,
            'message': 'Review too long'
        }, status=400)

    watched, _ = Watched.objects.get_or_create(
        user=request.user,
        movie=movie,
        defaults={'watched_date': timezone.now()}
    )
    watched.review = escape(review_text)
    watched.save()

    return JsonResponse({
        'success': True,
        'message': 'Review saved',
        'review': watched.review
    })


@require_POST
@login_required
def share_to_fediverse(request, movie_id):
    if not settings.ACTIVITYPUB_ENABLED:
        return JsonResponse({'success': False, 'message': 'Federation is disabled'}, status=403)

    profile = getattr(request.user, 'userprofile', None)
    if not profile or not profile.fedi_enabled:
        return JsonResponse({'success': False, 'message': 'Fediverse sharing is not enabled for your account'}, status=403)

    movie = get_object_or_404(Movie, id=movie_id)

    try:
        watched = Watched.objects.get(user=request.user, movie=movie)
    except Watched.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'You have not watched this movie'}, status=400)

    if watched.rating is None:
        return JsonResponse({'success': False, 'message': 'Rate the movie before sharing'}, status=400)

    stars = '★' * int(watched.rating) + '☆' * (5 - int(watched.rating))
    content = f'I just watched {escape(movie.title)} and gave it {stars}'

    from fedi.models import FediActivity, FediDelivery, FediFollower
    actor = request.user.fediactor
    base = settings.ACTIVITYPUB_DOMAIN.rstrip('/')
    activity_id = f'{base}/activities/{uuid.uuid4()}'
    note_id = f'{activity_id}/note'
    public = 'https://www.w3.org/ns/activitystreams#Public'
    movie_url = f'{base}/movies/details/{movie.id}'
    note = {
        'id': note_id,
        'type': 'Note',
        'attributedTo': actor.actor_id,
        'to': [public],
        'cc': [actor.followers_url],
        'content': content,
        'url': movie_url,
    }
    if movie.tmdb_poster_path:
        note['attachment'] = [{'type': 'Image', 'url': movie.tmdb_poster_path}]

    payload = {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'id': activity_id,
        'type': 'Create',
        'actor': actor.actor_id,
        'to': [public],
        'cc': [actor.followers_url],
        'object': note,
    }
    activity = FediActivity.objects.create(
        actor=actor, ap_id=activity_id, type='Create', payload=payload
    )
    followers = actor.followers.filter(state=FediFollower.ACCEPTED)
    for follower in followers:
        FediDelivery.objects.create(activity=activity, follower=follower)

    return JsonResponse({'success': True, 'message': 'Shared to your Fediverse followers'})