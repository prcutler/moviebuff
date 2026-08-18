from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from movies.models import Movie, Watched
from tv.models import TvSeason, TvShelf, TvShow

POSTER = "https://img.example/p.jpg"


@override_settings(ROOT_URLCONF="moviebuff.urls")
class DashboardTvSectionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        self.other = User.objects.create_user(username="bob", password="pwd")
        self.now = timezone.now()
        self.client.login(username="alice", password="pwd")

    def _movie(self, title, ago_days=0):
        movie = Movie.objects.create(
            tmdb_id=Movie.objects.count() + 1,
            title=title,
            overview="",
            release_date="2020-01-01",
            tmdb_poster_path=POSTER,
        )
        Watched.objects.create(
            user=self.user,
            movie=movie,
            watched_date=self.now - timedelta(days=ago_days),
            rating=4.0,
        )
        return movie

    def _tv(self, title, *, ago_days=0, user=None, rating=None):
        show = TvShow.objects.create(
            tmdb_id=TvShow.objects.count() + 1,
            title=title,
            tmdb_poster_path=POSTER,
        )
        TvShelf.objects.create(
            user=user or self.user,
            show=show,
            state=TvShelf.WATCHED,
            rating=rating,
            watched_date=self.now - timedelta(days=ago_days),
        )
        return show

    def test_dashboard_requires_login(self):
        """It shows one member's own shelves, so it must never be public."""
        self.client.logout()
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_dashboard_has_a_watched_tv_section(self):
        self._tv("Severance")
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Watched TV")
        self.assertContains(response, "Severance")

    def test_watched_movies_now_shows_only_four(self):
        for i in range(6):
            self._movie(f"Film {i}", ago_days=i)
        response = self.client.get("/dashboard/")
        self.assertEqual(len(response.context["watched_rows"]), 4)

    def test_tv_section_shows_four(self):
        for i in range(6):
            self._tv(f"Show {i}", ago_days=i)
        response = self.client.get("/dashboard/")
        self.assertEqual(len(response.context["tv_rows"]), 4)

    def test_tv_section_is_newest_first(self):
        self._tv("Oldest", ago_days=30)
        self._tv("Newest", ago_days=1)
        self._tv("Middle", ago_days=10)

        response = self.client.get("/dashboard/")
        titles = [row["title"] for row in response.context["tv_rows"]]
        self.assertEqual(titles, ["Newest", "Middle", "Oldest"])

    def test_only_your_own_tv_appears(self):
        self._tv("Mine", ago_days=2)
        self._tv("Theirs", ago_days=1, user=self.other)

        response = self.client.get("/dashboard/")
        titles = [row["title"] for row in response.context["tv_rows"]]
        self.assertEqual(titles, ["Mine"])

    def test_seasons_carry_their_show_name(self):
        show = TvShow.objects.create(
            tmdb_id=99, title="Severance", tmdb_poster_path=POSTER
        )
        season = TvSeason.objects.create(
            show=show, season_number=1, name="Season 1", tmdb_poster_path=POSTER
        )
        TvShelf.objects.create(
            user=self.user,
            season=season,
            state=TvShelf.WATCHED,
            watched_date=self.now,
        )
        response = self.client.get("/dashboard/")
        self.assertEqual(
            response.context["tv_rows"][0]["title"], "Severance — Season 1"
        )

    def test_unfinished_shows_are_excluded(self):
        show = TvShow.objects.create(
            tmdb_id=50, title="Still Going", tmdb_poster_path=POSTER
        )
        TvShelf.objects.create(
            user=self.user, show=show, state=TvShelf.WATCHING
        )
        response = self.client.get("/dashboard/")
        self.assertEqual(response.context["tv_rows"], [])

    def test_empty_section_invites_a_search(self):
        response = self.client.get("/dashboard/")
        self.assertContains(response, "Find a show")

    def test_ratings_render_as_stars(self):
        self._tv("Rated", rating=5.0)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.context["tv_rows"][0]["stars"], "★★★★★")


@override_settings(ROOT_URLCONF="moviebuff.urls")
class DashboardTvPaginationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        now = timezone.now()
        for i in range(6):
            show = TvShow.objects.create(
                tmdb_id=i + 1, title=f"Show {i}", tmdb_poster_path=POSTER
            )
            TvShelf.objects.create(
                user=self.user,
                show=show,
                state=TvShelf.WATCHED,
                watched_date=now - timedelta(days=i),
            )
        self.client.login(username="alice", password="pwd")

    def test_second_page_holds_the_remainder(self):
        response = self.client.get(
            "/dashboard/tv/?page=2", headers={"HX-Request": "true"}
        )
        self.assertEqual(response.status_code, 200)
        titles = [row["title"] for row in response.context["tv_rows"]]
        self.assertEqual(titles, ["Show 4", "Show 5"])

    def test_endpoint_returns_the_partial_only(self):
        response = self.client.get(
            "/dashboard/tv/?page=1", headers={"HX-Request": "true"}
        )
        self.assertContains(response, 'id="dashboard-tv-section"')
        self.assertNotContains(response, "<html")

    def test_endpoint_redirects_without_the_header(self):
        response = self.client.get("/dashboard/tv/?page=1")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/tv/shelf/watched/", response["Location"])

    def test_pagination_appears_only_when_needed(self):
        with_pages = self.client.get(
            "/dashboard/tv/?page=1", headers={"HX-Request": "true"}
        )
        self.assertContains(with_pages, "Watched TV pagination")

        TvShelf.objects.exclude(show__title="Show 0").delete()
        single = self.client.get(
            "/dashboard/tv/?page=1", headers={"HX-Request": "true"}
        )
        self.assertNotContains(single, "Watched TV pagination")

    def test_login_is_required(self):
        self.client.logout()
        response = self.client.get(
            "/dashboard/tv/?page=1", headers={"HX-Request": "true"}
        )
        self.assertEqual(response.status_code, 302)
