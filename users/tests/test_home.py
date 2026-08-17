from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from tv.models import TvSeason, TvShelf, TvShow
from users.views import _build_home_tv_context

POSTER = "https://img.example/p.jpg"


@override_settings(ROOT_URLCONF="moviebuff.urls")
class HomeTvSectionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        self.now = timezone.now()

    def _show(self, title, poster=POSTER, tmdb_id=None):
        return TvShow.objects.create(
            tmdb_id=tmdb_id or TvShow.objects.count() + 1,
            title=title,
            tmdb_poster_path=poster,
        )

    def _watched(self, *, show=None, season=None, ago_days=0, rating=None):
        return TvShelf.objects.create(
            user=self.user,
            show=show,
            season=season,
            state=TvShelf.WATCHED,
            rating=rating,
            watched_date=self.now - timedelta(days=ago_days),
        )

    def test_only_watched_entries_appear(self):
        show = self._show("Watched Show")
        other = self._show("Still Watching")
        self._watched(show=show)
        TvShelf.objects.create(
            user=self.user, show=other, state=TvShelf.WATCHING
        )

        titles = [c["title"] for c in _build_home_tv_context(1)["tv"]]
        self.assertEqual(titles, ["Watched Show"])

    def test_newest_first(self):
        for name, ago in [("Oldest", 30), ("Newest", 1), ("Middle", 10)]:
            self._watched(show=self._show(name), ago_days=ago)

        titles = [c["title"] for c in _build_home_tv_context(1)["tv"]]
        self.assertEqual(titles, ["Newest", "Middle", "Oldest"])

    def test_capped_at_four(self):
        for i in range(6):
            self._watched(show=self._show(f"Show {i}"), ago_days=i)
        self.assertEqual(len(_build_home_tv_context(1)["tv"]), 4)

    def test_shows_and_seasons_appear_together(self):
        show = self._show("Severance")
        season = TvSeason.objects.create(
            show=show, season_number=1, name="Season 1", tmdb_poster_path=POSTER
        )
        other = self._show("Andor")
        self._watched(season=season, ago_days=1)
        self._watched(show=other, ago_days=2)

        titles = [c["title"] for c in _build_home_tv_context(1)["tv"]]
        self.assertEqual(titles, ["Severance — Season 1", "Andor"])

    def test_season_without_a_name_falls_back_to_its_number(self):
        show = self._show("Severance")
        season = TvSeason.objects.create(
            show=show, season_number=2, tmdb_poster_path=POSTER
        )
        self._watched(season=season)

        self.assertEqual(
            _build_home_tv_context(1)["tv"][0]["title"], "Severance — Season 2"
        )

    def test_season_without_art_borrows_the_show_poster(self):
        show = self._show("Severance", poster=POSTER)
        season = TvSeason.objects.create(
            show=show, season_number=1, name="Season 1", tmdb_poster_path=""
        )
        self._watched(season=season)

        card = _build_home_tv_context(1)["tv"][0]
        self.assertEqual(card["poster"], POSTER)

    def test_entries_without_any_art_are_skipped(self):
        self._watched(show=self._show("No Art", poster=""))
        self.assertEqual(_build_home_tv_context(1)["tv"], [])

    def test_season_with_no_art_anywhere_is_skipped(self):
        show = self._show("Bare", poster="")
        season = TvSeason.objects.create(
            show=show, season_number=1, tmdb_poster_path=""
        )
        self._watched(season=season)
        self.assertEqual(_build_home_tv_context(1)["tv"], [])

    def test_rating_renders_as_stars(self):
        self._watched(show=self._show("Rated"), rating=4.0)
        self.assertEqual(_build_home_tv_context(1)["tv"][0]["stars"], "★★★★☆")

    def test_watched_without_a_rating_has_no_stars(self):
        self._watched(show=self._show("Unrated"))
        self.assertEqual(_build_home_tv_context(1)["tv"][0]["stars"], "")

    def test_missing_watched_date_falls_back_to_updated_at(self):
        """A row made outside the shelf views has no watched_date."""
        show = self._show("Admin Entry")
        TvShelf.objects.create(
            user=self.user, show=show, state=TvShelf.WATCHED, watched_date=None
        )
        titles = [c["title"] for c in _build_home_tv_context(1)["tv"]]
        self.assertEqual(titles, ["Admin Entry"])

    def test_links_point_at_the_right_page(self):
        show = self._show("Severance")
        season = TvSeason.objects.create(
            show=show, season_number=1, name="Season 1", tmdb_poster_path=POSTER
        )
        self._watched(season=season, ago_days=1)
        self._watched(show=self._show("Andor"), ago_days=2)

        cards = _build_home_tv_context(1)["tv"]
        self.assertIn(f"/tv/details/{show.id}/season/1/", cards[0]["url"])
        self.assertIn("/tv/details/", cards[1]["url"])

    def test_home_page_renders_the_section(self):
        self._watched(show=self._show("Severance"), rating=5.0)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recently Watched TV")
        self.assertContains(response, "Severance")

    def test_home_page_omits_the_section_when_empty(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Recently Watched TV")

    def test_movies_section_is_headed(self):
        from movies.models import Movie, Watched

        movie = Movie.objects.create(
            tmdb_id=1,
            title="The Martian",
            overview="Stranded.",
            release_date="2015-10-02",
            tmdb_poster_path="https://img.example/m.jpg",
        )
        Watched.objects.create(
            user=self.user, movie=movie, watched_date=self.now, rating=5.0
        )
        response = self.client.get("/")
        self.assertContains(response, "Recently Watched Movies")


@override_settings(ROOT_URLCONF="moviebuff.urls")
class HomeTvPaginationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        now = timezone.now()
        # Six entries: two pages of four.
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

    def test_page_counts(self):
        context = _build_home_tv_context(1)
        self.assertEqual(context["page"], 1)
        self.assertEqual(context["total_pages"], 2)
        self.assertEqual(len(context["tv"]), 4)

    def test_second_page_holds_the_remainder(self):
        context = _build_home_tv_context(2)
        self.assertEqual(context["page"], 2)
        self.assertEqual([c["title"] for c in context["tv"]], ["Show 4", "Show 5"])

    def test_out_of_range_page_clamps_to_last(self):
        self.assertEqual(_build_home_tv_context(99)["page"], 2)

    def test_htmx_endpoint_returns_the_partial(self):
        response = self.client.get("/home/tv/?page=2", headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Show 4")
        self.assertContains(response, 'id="home-tv"')
        # The partial only, not a full page.
        self.assertNotContains(response, "<html")

    def test_htmx_endpoint_redirects_without_the_header(self):
        response = self.client.get("/home/tv/?page=2")
        self.assertEqual(response.status_code, 302)

    def test_first_page_offers_next_but_not_previous(self):
        response = self.client.get("/home/tv/?page=1", headers={"HX-Request": "true"})
        self.assertContains(response, "Next")
        self.assertNotContains(response, "Previous")

    def test_last_page_offers_previous_but_not_next(self):
        response = self.client.get("/home/tv/?page=2", headers={"HX-Request": "true"})
        self.assertContains(response, "Previous")
        self.assertNotContains(response, "Next")
