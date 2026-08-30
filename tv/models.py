from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse


class TvShow(models.Model):
    """A series, anchored on TMDB the way ``movies.Movie`` is."""

    tmdb_id = models.IntegerField(null=True, blank=True, unique=True)
    title = models.CharField(max_length=255, blank=True, default="")
    overview = models.TextField(blank=True, default="")
    first_air_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=40, blank=True, default="")
    episode_runtime = models.PositiveIntegerField(null=True, blank=True)
    original_language = models.CharField(max_length=20, blank=True, default="")
    # Read for display, never joined on.
    networks = models.JSONField(default=list, blank=True)
    genres = models.JSONField(default=list, blank=True)
    tmdb_poster_path = models.TextField(blank=True, default="")
    tmdb_vote_average = models.FloatField(null=True, blank=True)
    tmdb_vote_count = models.IntegerField(null=True, blank=True)
    # Unix timestamp of the last TMDB refresh, matching Movie.last_updated.
    last_updated = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title", "pk"]

    def __str__(self):
        return self.title or f"TvShow<{self.pk}>"

    def get_absolute_url(self):
        return reverse("tv_show_details", args=[self.pk])


class TvSeason(models.Model):
    """A season, identified by its place under a show.

    TMDB gives a season no identifier that can be dereferenced on its own,
    so ``(show, season_number)`` is its identity.
    """

    show = models.ForeignKey(TvShow, on_delete=models.CASCADE, related_name="seasons")
    season_number = models.PositiveIntegerField()
    name = models.CharField(max_length=255, blank=True, default="")
    overview = models.TextField(blank=True, default="")
    air_date = models.DateField(null=True, blank=True)
    tmdb_poster_path = models.TextField(blank=True, default="")
    # What TMDB says the season holds. Kept so a season can show its length
    # without episode rows existing.
    episode_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["show", "season_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["show", "season_number"], name="uniq_tv_season_per_show"
            ),
        ]

    def __str__(self):
        return f"{self.show_id}:S{self.season_number}"

    def get_absolute_url(self):
        return reverse("tv_season_details", args=[self.show_id, self.season_number])


class TvShelf(models.Model):
    """A member's standing on one show or one season.

    Folds the movies app's Watchlist and Watched into a single row, because a
    series moves through states a film does not — you can be *watching* it, or
    have *dropped* it. One current row per member and subject.
    """

    WATCHLIST = "watchlist"
    WATCHING = "watching"
    WATCHED = "watched"
    DROPPED = "dropped"
    STATE_CHOICES = [
        (WATCHLIST, "Watchlist"),
        (WATCHING, "Watching"),
        (WATCHED, "Watched"),
        (DROPPED, "Dropped"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tv_shelves"
    )
    show = models.ForeignKey(
        TvShow,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="shelf_entries",
    )
    season = models.ForeignKey(
        TvSeason,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="shelf_entries",
    )
    state = models.CharField(max_length=10, choices=STATE_CHOICES)
    rating = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)],
    )
    review = models.TextField(blank=True, default="", max_length=300)
    # Whether this was a rewatch rather than a first time through.
    rewatch = models.BooleanField(default=False)
    # When the member finished it. Null until the state reaches "watched".
    watched_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(show__isnull=False, season__isnull=True)
                    | models.Q(show__isnull=True, season__isnull=False)
                ),
                name="tv_shelf_one_subject",
            ),
            models.CheckConstraint(
                condition=models.Q(rating__isnull=True)
                | models.Q(rating__gte=0.0, rating__lte=5.0),
                name="tv_shelf_rating_range",
            ),
            models.UniqueConstraint(
                fields=["user", "show"],
                condition=models.Q(show__isnull=False),
                name="uniq_tv_shelf_show",
            ),
            models.UniqueConstraint(
                fields=["user", "season"],
                condition=models.Q(season__isnull=False),
                name="uniq_tv_shelf_season",
            ),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.level}:{self.state}"

    @property
    def subject(self):
        """The show or season this row is about."""
        return self.season or self.show

    @property
    def level(self):
        """Either ``"season"`` or ``"show"``."""
        return "season" if self.season_id is not None else "show"

    @property
    def display_title(self):
        """How this row's subject is named in a post or a listing.

        A season carries its show's name too, since "Season 1" alone says
        nothing away from the show's own page.
        """
        if self.season_id is not None:
            season = self.season
            name = season.name or f"Season {season.season_number}"
            return f"{season.show.title} — {name}"
        return self.show.title

    @property
    def poster(self):
        """The poster to draw for this row, falling back to the show's."""
        if self.season_id is not None:
            return self.season.tmdb_poster_path or self.season.show.tmdb_poster_path
        return self.show.tmdb_poster_path

    def get_absolute_url(self):
        return self.subject.get_absolute_url()

    def clean(self):
        # Fail with a readable message rather than a raw constraint violation.
        chosen = [self.show_id, self.season_id]
        if sum(fk is not None for fk in chosen) != 1:
            raise ValidationError("Exactly one of show or season must be set.")
