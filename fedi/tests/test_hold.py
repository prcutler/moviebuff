"""A rating waits briefly so a review written just after joins the same post.

Delivery is already a separate step — notes sit queued until
``deliver_activities`` runs — so the window is a "do not send before" stamp
plus the rule that a still-held note is rewritten rather than duplicated.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from fedi.models import FediActivity, FediDelivery, FediFollower
from movies.models import Movie, Watched
from tv.models import TvSeason, TvShelf, TvShow


@override_settings(
    ACTIVITYPUB_ENABLED=True,
    ACTIVITYPUB_DOMAIN="https://example.com",
    ROOT_URLCONF="moviebuff.urls",
    FEDI_HOLD_SECONDS=120,
)
class HoldWindowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        profile = self.user.userprofile
        profile.fedi_enabled = True
        profile.save()
        self.movie = Movie.objects.create(
            tmdb_id=1,
            title="The Martian",
            overview="",
            release_date="2015-10-02",
            tmdb_poster_path="https://img.example/m.jpg",
        )

    def _rate(self, rating):
        watched = Watched.objects.create(
            user=self.user,
            movie=self.movie,
            watched_date=timezone.now(),
            rating=rating,
        )
        return watched

    def _only_note(self):
        self.assertEqual(FediActivity.objects.count(), 1)
        return FediActivity.objects.first().payload["object"]["content"]

    def _expire_holds(self):
        FediActivity.objects.update(hold_until=timezone.now() - timedelta(seconds=1))

    def test_rating_is_held_not_sent(self):
        self._rate(3.0)
        activity = FediActivity.objects.get()
        self.assertTrue(activity.is_held())
        self.assertEqual(activity.subject_key, f"movie:{self.movie.id}")

    def test_review_inside_the_window_folds_into_one_post(self):
        watched = self._rate(3.0)
        watched.review = "Loved it."
        watched.save()

        content = self._only_note()
        self.assertIn("rated The Martian", content)
        self.assertIn("Loved it.", content)

    def test_rating_corrected_inside_the_window_replaces_the_old_one(self):
        watched = self._rate(3.0)
        watched.rating = 4.0
        watched.save()

        content = self._only_note()
        self.assertIn("4.0/5", content)
        self.assertNotIn("3.0/5", content)

    def test_review_after_the_window_is_its_own_post(self):
        watched = self._rate(3.0)
        self._expire_holds()
        watched.review = "Second thoughts."
        watched.save()

        self.assertEqual(FediActivity.objects.count(), 2)
        newest = FediActivity.objects.order_by("-id").first()
        content = newest.payload["object"]["content"]
        self.assertIn("Second thoughts.", content)
        # The rating already reached followers; repeating it would double up.
        self.assertNotIn("rated The Martian", content)

    def test_form_saving_rating_and_review_together_makes_one_post(self):
        self.client.login(username="alice", password="pwd")
        self.client.post(
            f"/movies/watched/add/{self.movie.id}/",
            {
                "watched_date": "2026-08-17",
                "watched_time": "20:00",
                "rating": "5",
                "review": "Loved it.",
            },
        )
        content = self._only_note()
        self.assertIn("rated The Martian", content)
        self.assertIn("Loved it.", content)

    def test_a_different_movie_gets_its_own_note(self):
        other = Movie.objects.create(
            tmdb_id=2,
            title="Interstellar",
            overview="",
            release_date="2014-11-07",
            tmdb_poster_path="x",
        )
        self._rate(3.0)
        Watched.objects.create(
            user=self.user, movie=other, watched_date=timezone.now(), rating=4.0
        )
        self.assertEqual(FediActivity.objects.count(), 2)

    def test_another_member_does_not_fold_into_your_note(self):
        User = get_user_model()
        bob = User.objects.create_user(username="bob", password="pwd")
        profile = bob.userprofile
        profile.fedi_enabled = True
        profile.save()

        self._rate(3.0)
        Watched.objects.create(
            user=bob, movie=self.movie, watched_date=timezone.now(), rating=5.0
        )
        self.assertEqual(FediActivity.objects.count(), 2)

    @override_settings(FEDI_HOLD_SECONDS=0)
    def test_zero_hold_publishes_immediately(self):
        watched = self._rate(3.0)
        activity = FediActivity.objects.get()
        self.assertIsNone(activity.hold_until)
        self.assertFalse(activity.is_held())

        # With no window, a review becomes its own post as it did before.
        watched.review = "Loved it."
        watched.save()
        self.assertEqual(FediActivity.objects.count(), 2)


@override_settings(
    ACTIVITYPUB_ENABLED=True,
    ACTIVITYPUB_DOMAIN="https://example.com",
    ROOT_URLCONF="moviebuff.urls",
    FEDI_HOLD_SECONDS=120,
)
class TvHoldWindowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        profile = self.user.userprofile
        profile.fedi_enabled = True
        profile.save()
        self.show = TvShow.objects.create(
            tmdb_id=1, title="Severance", tmdb_poster_path="https://img.example/s.jpg"
        )
        self.season = TvSeason.objects.create(
            show=self.show, season_number=1, name="Season 1"
        )

    def test_season_rating_and_review_fold_into_one_post(self):
        shelf = TvShelf.objects.create(
            user=self.user, season=self.season, state=TvShelf.WATCHED, rating=4.0
        )
        shelf.review = "Unsettling."
        shelf.save()

        self.assertEqual(FediActivity.objects.count(), 1)
        content = FediActivity.objects.get().payload["object"]["content"]
        self.assertIn("Severance — Season 1", content)
        self.assertIn("Unsettling.", content)

    def test_show_and_season_are_separate_subjects(self):
        TvShelf.objects.create(
            user=self.user, show=self.show, state=TvShelf.WATCHED, rating=4.0
        )
        TvShelf.objects.create(
            user=self.user, season=self.season, state=TvShelf.WATCHED, rating=5.0
        )
        self.assertEqual(FediActivity.objects.count(), 2)


@override_settings(
    ACTIVITYPUB_ENABLED=True,
    ACTIVITYPUB_DOMAIN="https://example.com",
    ROOT_URLCONF="moviebuff.urls",
    FEDI_HOLD_SECONDS=120,
)
class DeliveryRespectsHoldTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        profile = self.user.userprofile
        profile.fedi_enabled = True
        profile.save()
        FediFollower.objects.create(
            actor=self.user.fediactor,
            remote_actor_id="https://remote.example/users/bob",
            inbox="https://remote.example/users/bob/inbox",
            state=FediFollower.ACCEPTED,
        )
        movie = Movie.objects.create(
            tmdb_id=1,
            title="The Martian",
            overview="",
            release_date="2015-10-02",
            tmdb_poster_path="x",
        )
        Watched.objects.create(
            user=self.user, movie=movie, watched_date=timezone.now(), rating=3.0
        )

    def _run(self, *args):
        out = StringIO()
        with patch("fedi.utils.requests.post") as mock_post:
            call_command("deliver_activities", *args, stdout=out)
        return out.getvalue(), mock_post.call_count

    def test_held_note_is_not_sent(self):
        output, calls = self._run()
        self.assertEqual(calls, 0)
        self.assertIn("Holding 1", output)
        self.assertEqual(
            FediDelivery.objects.get().status, FediDelivery.QUEUED
        )

    def test_note_is_sent_once_the_window_closes(self):
        FediActivity.objects.update(
            hold_until=timezone.now() - timedelta(seconds=1)
        )
        output, calls = self._run()
        self.assertEqual(calls, 1)
        self.assertEqual(FediDelivery.objects.get().status, FediDelivery.SENT)

    def test_ignore_holds_sends_immediately(self):
        output, calls = self._run("--ignore-holds")
        self.assertEqual(calls, 1)
        self.assertEqual(FediDelivery.objects.get().status, FediDelivery.SENT)
