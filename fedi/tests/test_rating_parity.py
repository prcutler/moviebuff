"""Movies and TV must announce a rating on the same terms.

The two signal handlers are written separately, so it is easy for one to
drift. These tests pin the shared contract: a rating announces whenever it
appears or changes, including on the row that first carries it, and nothing
announces without a rating or review to report.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from fedi.models import FediActivity
from movies.models import Movie, Watched
from tv.models import TvShow, TvShelf


@override_settings(
    ACTIVITYPUB_ENABLED=True,
    ACTIVITYPUB_DOMAIN="https://example.com",
    ROOT_URLCONF="moviebuff.urls",
)
class RatingParityTests(TestCase):
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
        self.show = TvShow.objects.create(
            tmdb_id=1, title="Severance", tmdb_poster_path="https://img.example/s.jpg"
        )

    def test_movie_created_with_a_rating_announces(self):
        Watched.objects.create(
            user=self.user,
            movie=self.movie,
            watched_date=timezone.now(),
            rating=5.0,
        )
        self.assertEqual(FediActivity.objects.count(), 1)

    def test_tv_created_with_a_rating_announces(self):
        TvShelf.objects.create(
            user=self.user, show=self.show, state=TvShelf.WATCHED, rating=5.0
        )
        self.assertEqual(FediActivity.objects.count(), 1)

    def test_movie_logged_without_a_rating_stays_quiet(self):
        Watched.objects.create(
            user=self.user, movie=self.movie, watched_date=timezone.now()
        )
        self.assertEqual(FediActivity.objects.count(), 0)

    def test_tv_shelved_without_a_rating_stays_quiet(self):
        TvShelf.objects.create(
            user=self.user, show=self.show, state=TvShelf.WATCHLIST
        )
        self.assertEqual(FediActivity.objects.count(), 0)

    def test_movie_rating_is_not_reannounced_on_an_unrelated_save(self):
        watched = Watched.objects.create(
            user=self.user,
            movie=self.movie,
            watched_date=timezone.now(),
            rating=5.0,
        )
        count = FediActivity.objects.count()
        watched.rewatch_count = 2
        watched.save()
        self.assertEqual(FediActivity.objects.count(), count)

    def test_tv_rating_is_not_reannounced_on_an_unrelated_save(self):
        shelf = TvShelf.objects.create(
            user=self.user, show=self.show, state=TvShelf.WATCHED, rating=5.0
        )
        count = FediActivity.objects.count()
        shelf.state = TvShelf.WATCHING
        shelf.save()
        self.assertEqual(FediActivity.objects.count(), count)

    def test_add_to_watched_form_announces_rating_and_review(self):
        """The regression this parity fix was really about.

        The form saves date, rating and review in one step, so a guard that
        skipped newly created rows swallowed both posts entirely.
        """
        self.client.login(username="alice", password="pwd")
        response = self.client.post(
            f"/movies/watched/add/{self.movie.id}/",
            {
                "watched_date": "2026-08-17",
                "watched_time": "20:00",
                "rating": "5",
                "review": "Loved it.",
            },
        )
        self.assertEqual(response.status_code, 302)

        contents = [
            a.payload["object"]["content"] for a in FediActivity.objects.all()
        ]
        self.assertEqual(len(contents), 2)
        self.assertTrue(any("rated" in c for c in contents))
        self.assertTrue(any("Loved it." in c for c in contents))

    def test_add_to_watched_form_without_a_rating_stays_quiet(self):
        self.client.login(username="alice", password="pwd")
        self.client.post(
            f"/movies/watched/add/{self.movie.id}/",
            {"watched_date": "2026-08-17", "watched_time": "20:00"},
        )
        self.assertEqual(FediActivity.objects.count(), 0)
