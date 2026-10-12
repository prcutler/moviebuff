from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from movies.models import Movie, Watchlist, Watched
from fedi.models import FediActivity


@override_settings(
    ACTIVITYPUB_ENABLED=True,
    ACTIVITYPUB_DOMAIN="https://example.com",
    ROOT_URLCONF="moviebuff.urls",
)
class MovieActivityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        profile = self.user.userprofile
        profile.fedi_enabled = True
        profile.save()
        self.movie = Movie.objects.create(
            tmdb_id=1,
            title="The Film",
            overview="Test",
            release_date="2020-01-01",
            tmdb_poster_path="https://img.example/film.jpg",
        )

    def test_watchlist_add_creates_activity(self):
        Watchlist.objects.create(user=self.user, movie=self.movie)
        activity = FediActivity.objects.order_by("-id").first()
        obj = activity.payload["object"]
        self.assertIn("added", obj["content"])
        self.assertEqual(obj["attachment"][0]["url"], self.movie.tmdb_poster_path)
        self.assertEqual(obj["url"], f"https://example.com/movies/details/{self.movie.id}")

    def test_watched_logged_creates_activity(self):
        watched = Watched.objects.create(
            user=self.user,
            movie=self.movie,
            watched_date=timezone.now(),
        )
        activity = FediActivity.objects.order_by("-id").first()
        obj = activity.payload["object"]
        self.assertIn("watched", obj["content"])
        self.assertIn(str(watched.watched_date.date()), obj["content"])

    def test_rating_updated_creates_activity(self):
        watched = Watched.objects.create(
            user=self.user,
            movie=self.movie,
            watched_date=timezone.now(),
        )
        FediActivity.objects.all().delete()
        watched.rating = 4.0
        watched.save()
        activity = FediActivity.objects.order_by("-id").first()
        obj = activity.payload["object"]
        self.assertIn("I just watched and rated The Film", obj["content"])
        self.assertIn("4.0", obj["content"])

    def test_rewatch_rating_uses_rewatched_text(self):
        watched = Watched.objects.create(
            user=self.user,
            movie=self.movie,
            watched_date=timezone.now(),
        )
        FediActivity.objects.all().delete()
        watched.rewatch_count += 1
        watched.rating = 4.0
        watched.save()
        activity = FediActivity.objects.order_by("-id").first()
        obj = activity.payload["object"]
        self.assertIn("I just re-watched and rated The Film", obj["content"])

    def test_review_created_creates_activity(self):
        watched = Watched.objects.create(
            user=self.user,
            movie=self.movie,
            watched_date=timezone.now(),
        )
        FediActivity.objects.all().delete()
        watched.review = "Great!"
        watched.save()
        activity = FediActivity.objects.order_by("-id").first()
        obj = activity.payload["object"]
        self.assertIn("Great!", obj["content"])
        self.assertIn("Read on MovieBuff", obj["content"])
        self.assertEqual(obj["url"], f"https://example.com/movies/details/{self.movie.id}")

    def test_no_activity_when_disabled(self):
        profile = self.user.userprofile
        profile.fedi_enabled = False
        profile.save()
        Watchlist.objects.create(user=self.user, movie=self.movie)
        self.assertEqual(FediActivity.objects.count(), 0)
