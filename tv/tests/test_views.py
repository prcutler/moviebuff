from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from tv.models import TvSeason, TvShelf, TvShow


@override_settings(ROOT_URLCONF="moviebuff.urls")
class TvPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        self.show = TvShow.objects.create(
            tmdb_id=1,
            title="Severance",
            overview="Work-life balance.",
            # Fresh enough that the page will not call out to TMDB.
            last_updated=9999999999,
        )
        self.season = TvSeason.objects.create(
            show=self.show, season_number=1, name="Season 1", episode_count=9
        )

    def test_show_page_renders_anonymously(self):
        response = self.client.get(f"/tv/details/{self.show.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Severance")
        self.assertContains(response, "Season 1")

    def test_season_page_renders(self):
        response = self.client.get(f"/tv/details/{self.show.id}/season/1/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Season 1")

    def test_unknown_season_is_404(self):
        response = self.client.get(f"/tv/details/{self.show.id}/season/99/")
        self.assertEqual(response.status_code, 404)

    def test_state_requires_login(self):
        response = self.client.post(
            f"/tv/state/{self.show.id}/", {"state": "watching"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TvShelf.objects.count(), 0)

    def test_set_and_clear_state(self):
        self.client.login(username="alice", password="pwd")
        self.client.post(f"/tv/state/{self.show.id}/", {"state": "watching"})
        shelf = TvShelf.objects.get(user=self.user, show=self.show)
        self.assertEqual(shelf.state, TvShelf.WATCHING)

        self.client.post(f"/tv/state/{self.show.id}/", {"state": ""})
        self.assertEqual(TvShelf.objects.count(), 0)

    def test_watched_state_stamps_a_date(self):
        self.client.login(username="alice", password="pwd")
        self.client.post(f"/tv/state/{self.show.id}/", {"state": "watched"})
        shelf = TvShelf.objects.get(user=self.user, show=self.show)
        self.assertIsNotNone(shelf.watched_date)

    def test_unknown_state_is_rejected(self):
        self.client.login(username="alice", password="pwd")
        response = self.client.post(
            f"/tv/state/{self.show.id}/", {"state": "nonsense"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(TvShelf.objects.count(), 0)

    def test_rating_creates_watched_entry(self):
        self.client.login(username="alice", password="pwd")
        self.client.post(f"/tv/rating/{self.show.id}/", {"rating": "4"})
        shelf = TvShelf.objects.get(user=self.user, show=self.show)
        self.assertEqual(shelf.rating, 4.0)
        self.assertEqual(shelf.state, TvShelf.WATCHED)

    def test_rating_out_of_range_is_rejected(self):
        self.client.login(username="alice", password="pwd")
        response = self.client.post(f"/tv/rating/{self.show.id}/", {"rating": "9"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(TvShelf.objects.count(), 0)

    def test_non_numeric_rating_is_rejected(self):
        self.client.login(username="alice", password="pwd")
        response = self.client.post(f"/tv/rating/{self.show.id}/", {"rating": "abc"})
        self.assertEqual(response.status_code, 400)

    def test_season_rating_is_separate_from_show(self):
        self.client.login(username="alice", password="pwd")
        self.client.post(f"/tv/rating/{self.show.id}/", {"rating": "3"})
        self.client.post(
            f"/tv/rating/{self.show.id}/season/1/", {"rating": "5"}
        )
        self.assertEqual(
            TvShelf.objects.get(user=self.user, show=self.show).rating, 3.0
        )
        self.assertEqual(
            TvShelf.objects.get(user=self.user, season=self.season).rating, 5.0
        )

    def test_review_is_truncated_to_field_limit(self):
        self.client.login(username="alice", password="pwd")
        self.client.post(f"/tv/review/{self.show.id}/", {"review": "x" * 500})
        shelf = TvShelf.objects.get(user=self.user, show=self.show)
        self.assertEqual(len(shelf.review), 300)

    def test_shelf_listing_shows_only_that_state(self):
        self.client.login(username="alice", password="pwd")
        TvShelf.objects.create(
            user=self.user, show=self.show, state=TvShelf.WATCHING
        )
        TvShelf.objects.create(
            user=self.user, season=self.season, state=TvShelf.WATCHED
        )

        watching = self.client.get("/tv/shelf/watching/")
        self.assertContains(watching, "Severance")
        watched = self.client.get("/tv/shelf/watched/")
        self.assertContains(watched, "Season 1")

    def test_unknown_shelf_state_redirects(self):
        self.client.login(username="alice", password="pwd")
        response = self.client.get("/tv/shelf/nonsense/")
        self.assertEqual(response.status_code, 302)

    def test_old_tv_search_url_redirects_to_unified_search(self):
        response = self.client.get("/tv/search/?q=severance")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/search/", response["Location"])
        self.assertIn("kind=tv", response["Location"])
        self.assertIn("q=severance", response["Location"])
