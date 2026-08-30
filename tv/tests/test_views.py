import re

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


@override_settings(ROOT_URLCONF="moviebuff.urls")
class TvRewatchTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        self.show = TvShow.objects.create(
            tmdb_id=1, title="Severance", last_updated=9999999999
        )
        self.season = TvSeason.objects.create(
            show=self.show, season_number=1, name="Season 1"
        )
        self.client.login(username="alice", password="pwd")

    def test_checked_means_yes(self):
        self.client.post(f"/tv/rewatch/{self.show.id}/", {"rewatch": "on"})
        self.assertTrue(TvShelf.objects.get(user=self.user, show=self.show).rewatch)

    def test_unchecked_means_no(self):
        self.client.post(f"/tv/rewatch/{self.show.id}/", {"rewatch": "on"})
        self.client.post(f"/tv/rewatch/{self.show.id}/", {})
        self.assertFalse(TvShelf.objects.get(user=self.user, show=self.show).rewatch)

    def test_defaults_to_no(self):
        self.client.post(f"/tv/state/{self.show.id}/", {"state": "watched"})
        self.assertFalse(TvShelf.objects.get(user=self.user, show=self.show).rewatch)

    def test_seasons_track_it_separately_from_the_show(self):
        self.client.post(f"/tv/rewatch/{self.show.id}/season/1/", {"rewatch": "on"})
        self.client.post(f"/tv/rewatch/{self.show.id}/", {})

        self.assertTrue(
            TvShelf.objects.get(user=self.user, season=self.season).rewatch
        )
        self.assertFalse(
            TvShelf.objects.get(user=self.user, show=self.show).rewatch
        )

    def test_setting_it_does_not_disturb_rating_or_review(self):
        self.client.post(f"/tv/rating/{self.show.id}/", {"rating": "4"})
        self.client.post(f"/tv/review/{self.show.id}/", {"review": "Great."})
        self.client.post(f"/tv/rewatch/{self.show.id}/", {"rewatch": "on"})

        shelf = TvShelf.objects.get(user=self.user, show=self.show)
        self.assertEqual(shelf.rating, 4.0)
        self.assertEqual(shelf.review, "Great.")
        self.assertTrue(shelf.rewatch)

    def test_requires_login(self):
        self.client.logout()
        response = self.client.post(
            f"/tv/rewatch/{self.show.id}/", {"rewatch": "on"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TvShelf.objects.count(), 0)

    def test_checkbox_appears_on_show_and_season_pages(self):
        for url in [
            f"/tv/details/{self.show.id}/",
            f"/tv/details/{self.show.id}/season/1/",
        ]:
            response = self.client.get(url)
            self.assertContains(response, 'name="rewatch"')
            self.assertContains(response, "Re-watch")

    def _rewatch_input(self, url):
        """The rewatch checkbox element itself, so 'checked' can't match elsewhere."""
        html = self.client.get(url).content.decode()
        match = re.search(r'<input[^>]*id="rewatch-[^"]*"[^>]*>', html)
        self.assertIsNotNone(match, f"no rewatch checkbox on {url}")
        return match.group(0)

    def test_checkbox_stays_ticked_on_a_later_visit(self):
        url = f"/tv/details/{self.show.id}/"
        self.assertNotIn("checked", self._rewatch_input(url))

        self.client.post(f"/tv/rewatch/{self.show.id}/", {"rewatch": "on"})
        self.assertIn("checked", self._rewatch_input(url))

    def test_unticking_clears_it_on_a_later_visit(self):
        url = f"/tv/details/{self.show.id}/"
        self.client.post(f"/tv/rewatch/{self.show.id}/", {"rewatch": "on"})
        self.client.post(f"/tv/rewatch/{self.show.id}/", {})
        self.assertNotIn("checked", self._rewatch_input(url))

    def test_a_ticked_season_does_not_tick_its_show(self):
        self.client.post(
            f"/tv/rewatch/{self.show.id}/season/1/", {"rewatch": "on"}
        )
        season = self._rewatch_input(f"/tv/details/{self.show.id}/season/1/")
        show = self._rewatch_input(f"/tv/details/{self.show.id}/")
        self.assertIn("checked", season)
        self.assertNotIn("checked", show)

    def test_another_member_does_not_see_your_tick(self):
        self.client.post(f"/tv/rewatch/{self.show.id}/", {"rewatch": "on"})
        User = get_user_model()
        User.objects.create_user(username="bob", password="pwd")
        self.client.login(username="bob", password="pwd")
        self.assertNotIn(
            "checked", self._rewatch_input(f"/tv/details/{self.show.id}/")
        )

    def test_rewatch_alone_does_not_federate(self):
        from fedi.models import FediActivity

        profile = self.user.userprofile
        profile.fedi_enabled = True
        profile.save()
        with override_settings(
            ACTIVITYPUB_ENABLED=True, ACTIVITYPUB_DOMAIN="https://example.com"
        ):
            self.client.post(f"/tv/rewatch/{self.show.id}/", {"rewatch": "on"})
            self.assertEqual(FediActivity.objects.count(), 0)


@override_settings(ROOT_URLCONF="moviebuff.urls")
class PublicShelfTests(TestCase):
    """A visitor sees the tracking facts, read-only, on show and season pages."""

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="alice", password="pwd")
        self.show = TvShow.objects.create(
            tmdb_id=1, title="Severance", last_updated=9999999999
        )
        self.season = TvSeason.objects.create(
            show=self.show, season_number=1, name="Season 1"
        )
        self.show_url = f"/tv/details/{self.show.id}/"
        self.season_url = f"/tv/details/{self.show.id}/season/1/"

    def _shelf(self, **kwargs):
        kwargs.setdefault("show", self.show)
        return TvShelf.objects.create(user=self.owner, **kwargs)

    def test_visitor_sees_status_rewatch_rating_and_review(self):
        self._shelf(
            state=TvShelf.WATCHED,
            rating=5.0,
            review="Unsettling.",
            rewatch=True,
        )
        response = self.client.get(self.show_url)
        self.assertContains(response, "Watched")
        self.assertContains(response, "<strong>Re-watch:</strong> Y", html=False)
        self.assertContains(response, "5.0/5")
        self.assertContains(response, "Unsettling.")

    def test_visitor_sees_not_rated_when_unrated(self):
        self._shelf(state=TvShelf.WATCHING)
        self.assertContains(self.client.get(self.show_url), "Not rated")

    def test_visitor_gets_no_controls(self):
        self._shelf(state=TvShelf.WATCHED, rating=4.0)
        html = self.client.get(self.show_url).content.decode()
        for control in ['name="rewatch"', 'name="rating"', 'name="review"', 'name="state"']:
            self.assertNotIn(control, html, f"{control} offered to a visitor")

    def test_seasons_show_their_own_tracking(self):
        self._shelf(show=None, season=self.season, state=TvShelf.WATCHED, rating=3.0)
        self.assertContains(self.client.get(self.season_url), "3.0/5")
        # The show itself has no entry, so nothing is claimed for it.
        self.assertNotContains(self.client.get(self.show_url), "Not rated")

    def test_nothing_is_shown_when_untracked(self):
        response = self.client.get(self.show_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<strong>Re-watch:</strong>", html=False)

    def test_the_owner_still_gets_the_controls(self):
        self._shelf(state=TvShelf.WATCHED, rating=4.0)
        self.client.login(username="alice", password="pwd")
        html = self.client.get(self.show_url).content.decode()
        for control in ['name="rewatch"', 'name="rating"', 'name="review"', 'name="state"']:
            self.assertIn(control, html)
