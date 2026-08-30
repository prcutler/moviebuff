from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator


class Movie(models.Model):
    tmdb_id = models.IntegerField(null=True, blank=True)
    title = models.CharField(max_length=255)
    overview = models.TextField()
    release_date = models.DateField()
    original_language = models.TextField(null=True, blank=True)
    budget = models.TextField(null=True, blank=True)
    runtime = models.TextField(null=True, blank=True)
    tmdb_poster_path = models.TextField()
    tmdb_vote_average = models.IntegerField(null=True, blank=True)
    tmdb_vote_count = models.IntegerField(null=True, blank=True)
    imdb_id = models.TextField(null=True, blank=True)
    last_updated = models.IntegerField(null=True, blank=True)


class Watched(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    watched_date = models.DateTimeField()
    # Whether this viewing was a rewatch. The count below still tracks how
    # many times, so a member who had rewatched something keeps that history.
    rewatch = models.BooleanField(default=False)
    rewatch_count = models.PositiveIntegerField(default=1)
    rating = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)],
        null=True,
        blank=True
    )
    review = models.TextField(max_length=300, blank=True)


class Watchlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    added_date = models.DateTimeField(auto_now_add=True)


class CustomWatchlist(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_custom_watchlists')
    created_at = models.DateTimeField(auto_now_add=True)
    users = models.ManyToManyField(User, related_name='shared_custom_watchlists', blank=True)


class CustomWatchlistItem(models.Model):
    watchlist = models.ForeignKey(CustomWatchlist, on_delete=models.CASCADE, related_name='items')
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    added_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='added_watchlist_items')
    added_date = models.DateTimeField(auto_now_add=True)

