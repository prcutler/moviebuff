from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from movies.models import Movie, Watched
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
        self.assertIn("rated", obj["content"])
        self.assertIn("4.0", obj["content"])

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
        """Rating and reviewing must stay silent for an opted-out member.

        Driven by a rating and a review rather than a watchlist add: those
        are the actions that do federate, so this fails if the opt-out check
        ever breaks. A watchlist add announces nothing either way.
        """
        profile = self.user.userprofile
        profile.fedi_enabled = False
        profile.save()

        watched = Watched.objects.create(
            user=self.user,
            movie=self.movie,
            watched_date=timezone.now(),
            rating=5.0,
        )
        self.assertEqual(FediActivity.objects.count(), 0)

        watched.review = "Great!"
        watched.save()
        self.assertEqual(FediActivity.objects.count(), 0)

    def test_the_same_actions_do_federate_when_enabled(self):
        """Guards the test above: proves those actions are not silent anyway."""
        watched = Watched.objects.create(
            user=self.user,
            movie=self.movie,
            watched_date=timezone.now(),
            rating=5.0,
        )
        self.assertEqual(FediActivity.objects.count(), 1)

        # Inside the hold window, the review folds into the same note.
        watched.review = "Great!"
        watched.save()
        content = FediActivity.objects.get().payload["object"]["content"]
        self.assertIn("rated", content)
        self.assertIn("Great!", content)
