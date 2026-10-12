import time
import uuid
from urllib.parse import urlencode
from django.db.models import Avg
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.timezone import localtime
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils.html import escape
from .models import Movie, Watched, Watchlist, CustomWatchlist, CustomWatchlistItem
from connectors.tmdb_connector import TMDbConnector
from django.conf import settings
from .forms import WatchedForm, WatchlistForm

def search_movies(request):
    """Kept so old links still work; movie search now lives in the one search."""
    params = urlencode({'q': request.GET.get('q', ''), 'kind': 'movie'})
    return redirect(f"{reverse('search')}?{params}")

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

    # Calculate public stats (available to all visitors)
    total_reviews = Watched.objects.filter(movie=movie, review__isnull=False).count()
    average_rating = Watched.objects.filter(movie=movie, rating__isnull=False).aggregate(Avg('rating'))['rating__avg']
    other_reviews = Watched.objects.filter(movie=movie, review__isnull=False).exclude(review__exact='').order_by('-watched_date')

    # Public rating (first rated entry for this movie)
    public_watched = Watched.objects.filter(movie=movie, rating__isnull=False).first()
    public_rating = int(public_watched.rating) if public_watched else 0

    is_in_watchlist = False
    custom_watchlists = []

    if request.user.is_authenticated:
        watched_entry = Watched.objects.filter(user=request.user, movie=movie).first()
        is_in_watchlist = Watchlist.objects.filter(user=request.user, movie=movie).exists()
        custom_watchlists = CustomWatchlist.objects.filter(items__movie=movie, users=request.user).distinct()
    else:
        # This is one member's catalogue, so the entry is shown to visitors
        # the way the reviews below already are — read-only, no controls.
        # Watchlist membership stays private: it is a plan, not a record.
        watched_entry = Watched.objects.filter(movie=movie).order_by('id').first()

    is_watched = watched_entry is not None
    user_rating = (
        int(watched_entry.rating)
        if watched_entry and watched_entry.rating is not None
        else 0
    )

    return render(request, 'movies/movie_details.html', {
        'movie': movie,
        'public_rating': public_rating,
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
        watched = Watched.objects.create(
            user=request.user,
            movie=movie,
            watched_date=timezone.now(),
            rewatch=bool(request.POST.get('rewatch')),
        )
        return JsonResponse({
            'success': True,
            'message': 'Added to watched',
            'new_label': 'Remove from Watched',
            **_watched_facts(watched),
        })

def add_to_watched(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    existing = Watched.objects.filter(user=request.user, movie=movie).first()
    if request.method == 'POST':
        form = WatchedForm(request.POST)
        if form.is_valid():
            is_rewatch = form.cleaned_data.get('rewatch')
            instance = form.save(commit=False)
            if existing:
                if is_rewatch:
                    existing.rewatch_count += 1
                existing.rewatch = is_rewatch
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
    _apply_rewatch(watched, request)
    watched.save()

    return JsonResponse({
        'success': True,
        'message': 'Rating saved',
        'rating': rating,
        **_watched_facts(watched),
    })


def _watched_facts(watched):
    """What the User Data block needs to show an entry it did not render.

    Matches the template's own formatting, so a block revealed by script
    reads the same as one drawn by the server.
    """
    return {
        'rewatch': watched.rewatch,
        'watched_date': localtime(watched.watched_date).strftime('%m/%d/%Y %H:%M'),
    }


def _apply_rewatch(watched, request):
    """Carry the Re-watch checkbox onto ``watched`` when the request sent it.

    Rating and reviewing both create the entry via get_or_create, so a box
    ticked before either of those would otherwise be lost. The key is only
    honoured when present, so a caller that never sends it cannot clear a
    flag the member set elsewhere.
    """
    if 'rewatch' in request.POST:
        watched.rewatch = bool(request.POST.get('rewatch'))


@login_required
@require_POST
def update_rewatch(request, movie_id):
    """Change the rewatch flag on a movie already marked watched.

    Unlike the rating, this does not create an entry: ticking a box is not a
    claim to have seen something. Adding a movie carries its own checkbox.
    """
    movie = get_object_or_404(Movie, id=movie_id)
    watched = Watched.objects.filter(user=request.user, movie=movie).first()
    if watched is None:
        return JsonResponse({
            'success': False,
            'message': 'Mark it as watched first',
        }, status=400)

    watched.rewatch = bool(request.POST.get('rewatch'))
    watched.save()
    return JsonResponse({
        'success': True,
        'message': 'Re-watch saved',
        **_watched_facts(watched),
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
    _apply_rewatch(watched, request)
    watched.save()

    return JsonResponse({
        'success': True,
        'message': 'Review saved',
        'review': watched.review,
        **_watched_facts(watched),
    })


@login_required
def share_button_partial(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    try:
        watched = Watched.objects.get(user=request.user, movie=movie)
    except Watched.DoesNotExist:
        watched = None
    show = watched is not None and watched.rating is not None
    return render(request, 'movies/partials/share_button.html', {
        'movie': movie,
        'show': show,
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
    verb = 're-watched' if watched.rewatch else 'watched'
    content = f'I just {verb} and rated {escape(movie.title)} {stars}'

    from fedi.models import FediActivity, FediDelivery, FediFollower
    from fedi.vocab import NOTE_CONTEXT, build_interaction_policy
    actor = request.user.fediactor
    base = settings.ACTIVITYPUB_DOMAIN.rstrip('/')
    activity_id = f'{base}/activities/{uuid.uuid4()}'
    note_id = activity_id
    public = 'https://www.w3.org/ns/activitystreams#Public'
    movie_url = f'{base}/movies/details/{movie.id}'
    from django.utils import timezone
    now = timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    note = {
        'id': note_id,
        'type': 'Note',
        'published': now,
        'attributedTo': actor.actor_id,
        'to': [public],
        'cc': [actor.followers_url],
        'content': content,
        'mediaType': 'text/html',
        'tag': [],
        'url': movie_url,
        'interactionPolicy': build_interaction_policy(actor),
    }
    if movie.tmdb_poster_path:
        note['attachment'] = [{'type': 'Image', 'url': movie.tmdb_poster_path}]

    payload = {
        '@context': NOTE_CONTEXT,
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