from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from movies.models import Movie, Watched, Watchlist
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
        self.assertEqual(len(response.context["tv_watched"]["rows"]), 4)

    def test_tv_section_is_newest_first(self):
        self._tv("Oldest", ago_days=30)
        self._tv("Newest", ago_days=1)
        self._tv("Middle", ago_days=10)

        response = self.client.get("/dashboard/")
        titles = [row["title"] for row in response.context["tv_watched"]["rows"]]
        self.assertEqual(titles, ["Newest", "Middle", "Oldest"])

    def test_only_your_own_tv_appears(self):
        self._tv("Mine", ago_days=2)
        self._tv("Theirs", ago_days=1, user=self.other)

        response = self.client.get("/dashboard/")
        titles = [row["title"] for row in response.context["tv_watched"]["rows"]]
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
            response.context["tv_watched"]["rows"][0]["title"], "Severance — Season 1"
        )

    def test_unfinished_shows_are_excluded(self):
        show = TvShow.objects.create(
            tmdb_id=50, title="Still Going", tmdb_poster_path=POSTER
        )
        TvShelf.objects.create(
            user=self.user, show=show, state=TvShelf.WATCHING
        )
        response = self.client.get("/dashboard/")
        self.assertEqual(response.context["tv_watched"]["rows"], [])

    def test_empty_section_invites_a_search(self):
        response = self.client.get("/dashboard/")
        self.assertContains(response, "Find a show")

    def test_ratings_render_as_stars(self):
        self._tv("Rated", rating=5.0)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.context["tv_watched"]["rows"][0]["stars"], "★★★★★")


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
        titles = [row["title"] for row in response.context["ctx"]["rows"]]
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


@override_settings(ROOT_URLCONF="moviebuff.urls")
class DashboardWatchlistTests(TestCase):
    """One Watchlist: films queued up, series already underway."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        self.other = User.objects.create_user(username="bob", password="pwd")
        self.now = timezone.now()
        self.client.login(username="alice", password="pwd")

    def _queued_movie(self, title, *, ago_days=0, user=None):
        movie = Movie.objects.create(
            tmdb_id=Movie.objects.count() + 1,
            title=title,
            overview="",
            release_date="2020-01-01",
            tmdb_poster_path=POSTER,
        )
        entry = Watchlist.objects.create(user=user or self.user, movie=movie)
        Watchlist.objects.filter(pk=entry.pk).update(
            added_date=self.now - timedelta(days=ago_days)
        )
        return movie

    def _shelf(self, title, *, state=TvShelf.WATCHING, ago_days=0, user=None, season=False):
        show = TvShow.objects.create(
            tmdb_id=TvShow.objects.count() + 1,
            title=title,
            tmdb_poster_path=POSTER,
        )
        kwargs = {"show": show}
        if season:
            kwargs = {
                "season": TvSeason.objects.create(
                    show=show, season_number=1, name="Season 1",
                    tmdb_poster_path=POSTER,
                )
            }
        entry = TvShelf.objects.create(
            user=user or self.user, state=state, **kwargs
        )
        TvShelf.objects.filter(pk=entry.pk).update(
            updated_at=self.now - timedelta(days=ago_days)
        )
        return show

    def _rows(self):
        return self.client.get("/dashboard/").context["watchlist_rows"]

    def test_movies_and_series_share_one_section(self):
        self._queued_movie("Queued Film", ago_days=2)
        self._shelf("Underway Series", ago_days=1)

        response = self.client.get("/dashboard/")
        titles = [r["title"] for r in response.context["watchlist_rows"]]
        self.assertEqual(titles, ["Underway Series", "Queued Film"])

    def test_the_standalone_progress_section_is_gone(self):
        self._shelf("Underway Series")
        response = self.client.get("/dashboard/")
        self.assertNotContains(response, "TV In Progress")
        self.assertContains(response, "Watchlist")

    def test_each_kind_is_labelled(self):
        self._queued_movie("Queued Film")
        self._shelf("Underway Series")
        response = self.client.get("/dashboard/")
        self.assertContains(response, "In progress")
        self.assertContains(response, "Movie")

    def test_only_series_in_progress_appear(self):
        self._shelf("Underway", state=TvShelf.WATCHING)
        self._shelf("Finished", state=TvShelf.WATCHED)
        self._shelf("Abandoned", state=TvShelf.DROPPED)
        self._shelf("Queued Show", state=TvShelf.WATCHLIST)

        self.assertEqual([r["title"] for r in self._rows()], ["Underway"])

    def test_seasons_in_progress_appear(self):
        self._shelf("Severance", season=True)
        self.assertEqual(self._rows()[0]["title"], "Severance — Season 1")

    def test_only_your_own_entries_appear(self):
        self._queued_movie("Mine", ago_days=2)
        self._queued_movie("Theirs", ago_days=1, user=self.other)
        self._shelf("Their Series", ago_days=0, user=self.other)

        self.assertEqual([r["title"] for r in self._rows()], ["Mine"])

    def test_newest_first_across_both_kinds(self):
        self._queued_movie("Film Old", ago_days=9)
        self._shelf("Series Newest", ago_days=1)
        self._queued_movie("Film Recent", ago_days=3)
        self._shelf("Series Older", ago_days=6)

        self.assertEqual(
            [r["title"] for r in self._rows()],
            ["Series Newest", "Film Recent", "Series Older", "Film Old"],
        )

    def test_paginates_across_the_merged_list(self):
        for i in range(6):
            self._queued_movie(f"Film {i}", ago_days=i * 2)
        for i in range(6):
            self._shelf(f"Series {i}", ago_days=i * 2 + 1)

        first = self._rows()
        self.assertEqual(len(first), 8)

        response = self.client.get(
            "/dashboard/watchlist/?page=2", headers={"HX-Request": "true"}
        )
        self.assertEqual(response.status_code, 200)
        second = response.context["watchlist_rows"]
        self.assertEqual(len(second), 4)
        # A page boundary must not lose or repeat anything.
        titles = [r["title"] for r in first] + [r["title"] for r in second]
        self.assertEqual(len(titles), len(set(titles)), "duplicate across pages")
        self.assertEqual(len(titles), 12)

    def test_htmx_endpoint_returns_the_partial_only(self):
        self._queued_movie("Queued Film")
        response = self.client.get(
            "/dashboard/watchlist/", headers={"HX-Request": "true"}
        )
        self.assertContains(response, 'id="dashboard-watchlist-section"')
        self.assertNotContains(response, "<html")

    def test_htmx_endpoint_redirects_without_the_header(self):
        response = self.client.get("/dashboard/watchlist/")
        self.assertEqual(response.status_code, 302)

    def test_empty_watchlist_invites_a_search(self):
        response = self.client.get("/dashboard/")
        self.assertContains(response, "start by making a")
