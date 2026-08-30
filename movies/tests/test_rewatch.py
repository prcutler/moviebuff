import time

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from movies.forms import WatchedForm
from movies.models import Movie, Watched


@override_settings(ROOT_URLCONF="moviebuff.urls")
class MovieRewatchTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        self.movie = Movie.objects.create(
            tmdb_id=1,
            title="The Martian",
            overview="",
            release_date="2015-10-02",
            tmdb_poster_path="https://img.example/m.jpg",
        )
        self.client.login(username="alice", password="pwd")

    def _post(self, **extra):
        data = {"watched_date": "2026-08-17", "watched_time": "20:00"}
        data.update(extra)
        return self.client.post(f"/movies/watched/add/{self.movie.id}/", data)

    def test_form_exposes_the_rewatch_field(self):
        self.assertIn("rewatch", WatchedForm().fields)
        self.assertEqual(WatchedForm().fields["rewatch"].label, "Re-watch")

    def test_unchecked_means_no(self):
        self._post()
        self.assertFalse(Watched.objects.get().rewatch)

    def test_checked_means_yes(self):
        self._post(rewatch="on")
        self.assertTrue(Watched.objects.get().rewatch)

    def test_a_new_entry_records_the_flag(self):
        """It used to be dropped entirely for a first-time entry."""
        self._post(rewatch="on")
        watched = Watched.objects.get()
        self.assertTrue(watched.rewatch)
        self.assertEqual(watched.rewatch_count, 1)

    def test_rewatching_an_existing_entry_bumps_the_count(self):
        Watched.objects.create(
            user=self.user, movie=self.movie, watched_date=timezone.now()
        )
        self._post(rewatch="on")
        watched = Watched.objects.get()
        self.assertTrue(watched.rewatch)
        self.assertEqual(watched.rewatch_count, 2)

    def test_unchecking_clears_the_flag_but_keeps_the_count(self):
        Watched.objects.create(
            user=self.user,
            movie=self.movie,
            watched_date=timezone.now(),
            rewatch=True,
            rewatch_count=3,
        )
        self._post()
        watched = Watched.objects.get()
        self.assertFalse(watched.rewatch)
        self.assertEqual(watched.rewatch_count, 3)

    def test_the_checkbox_is_on_the_form_page(self):
        response = self.client.get(f"/movies/watched/add/{self.movie.id}/")
        self.assertContains(response, 'name="rewatch"')
        self.assertContains(response, "Re-watch")
        # The old ad-hoc field name is gone.
        self.assertNotContains(response, 'name="is_rewatch"')

    def test_ticking_rewatch_does_not_federate_on_its_own(self):
        """Only ratings and reviews announce; a rewatch flag is not news."""
        from fedi.models import FediActivity

        profile = self.user.userprofile
        profile.fedi_enabled = True
        profile.save()
        with override_settings(
            ACTIVITYPUB_ENABLED=True, ACTIVITYPUB_DOMAIN="https://example.com"
        ):
            self._post(rewatch="on")
            self.assertEqual(FediActivity.objects.count(), 0)


@override_settings(ROOT_URLCONF="moviebuff.urls")
class ToggleWatchedRewatchTests(TestCase):
    """The Add to Watched button on the details page carries the checkbox."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        # Every field populated and a fresh timestamp, so the details view
        # considers the row current and does not call out to TMDB.
        self.movie = Movie.objects.create(
            tmdb_id=1,
            title="The Martian",
            overview="Stranded.",
            release_date="2015-10-02",
            original_language="en",
            budget="108000000",
            runtime="144",
            tmdb_vote_average=8,
            tmdb_vote_count=1000,
            imdb_id="tt3659388",
            tmdb_poster_path="https://img.example/m.jpg",
            last_updated=int(time.time()),
        )
        self.client.login(username="alice", password="pwd")

    def test_adding_with_the_box_ticked_records_yes(self):
        response = self.client.post(
            f"/movies/watched/toggle/{self.movie.id}/", {"rewatch": "on"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Watched.objects.get().rewatch)

    def test_adding_without_it_records_no(self):
        self.client.post(f"/movies/watched/toggle/{self.movie.id}/")
        self.assertFalse(Watched.objects.get().rewatch)

    def test_the_checkbox_is_on_the_details_page(self):
        response = self.client.get(f"/movies/details/{self.movie.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="rewatch-check"')
        self.assertContains(response, "Re-watch")

    def test_the_checkbox_is_hidden_once_watched(self):
        """Removing an entry has no rewatch to record."""
        Watched.objects.create(
            user=self.user, movie=self.movie, watched_date=timezone.now()
        )
        response = self.client.get(f"/movies/details/{self.movie.id}/")
        self.assertContains(response, 'id="rewatch-wrap" class="form-check mt-2 d-none"')

    def test_the_checkbox_is_visible_when_not_watched(self):
        response = self.client.get(f"/movies/details/{self.movie.id}/")
        self.assertContains(response, 'id="rewatch-wrap" class="form-check mt-2"')

    def test_a_recorded_rewatch_reads_yes(self):
        Watched.objects.create(
            user=self.user,
            movie=self.movie,
            watched_date=timezone.now(),
            rewatch=True,
        )
        response = self.client.get(f"/movies/details/{self.movie.id}/")
        self.assertContains(response, "<strong>Re-watch:</strong> Y", html=False)

    def test_a_first_viewing_reads_no(self):
        Watched.objects.create(
            user=self.user, movie=self.movie, watched_date=timezone.now()
        )
        response = self.client.get(f"/movies/details/{self.movie.id}/")
        self.assertContains(response, "<strong>Re-watch:</strong> N", html=False)

    def test_the_line_is_absent_until_watched(self):
        """User Data has no watched entry to describe yet."""
        response = self.client.get(f"/movies/details/{self.movie.id}/")
        self.assertNotContains(response, "<strong>Re-watch:</strong>", html=False)

    def test_the_line_sits_under_watched_date(self):
        Watched.objects.create(
            user=self.user, movie=self.movie, watched_date=timezone.now()
        )
        html = self.client.get(
            f"/movies/details/{self.movie.id}/"
        ).content.decode()
        self.assertLess(
            html.index("Watched Date:"), html.index("<strong>Re-watch:</strong>")
        )

    def test_removing_then_re_adding_keeps_the_new_choice(self):
        self.client.post(
            f"/movies/watched/toggle/{self.movie.id}/", {"rewatch": "on"}
        )
        self.client.post(f"/movies/watched/toggle/{self.movie.id}/")  # removes
        self.assertEqual(Watched.objects.count(), 0)

        self.client.post(f"/movies/watched/toggle/{self.movie.id}/")  # re-adds
        self.assertFalse(Watched.objects.get().rewatch)

    def test_the_button_names_its_checkbox(self):
        """The JS reads data-checkbox to know what to send."""
        response = self.client.get(f"/movies/details/{self.movie.id}/")
        self.assertContains(response, 'data-checkbox="rewatch-check"')


@override_settings(ROOT_URLCONF="moviebuff.urls")
class MovieDetailsAnonymousTests(TestCase):
    """A logged-out visitor must not be served JS for controls they lack."""

    def setUp(self):
        self.movie = Movie.objects.create(
            tmdb_id=1,
            title="The Martian",
            overview="Stranded.",
            release_date="2015-10-02",
            original_language="en",
            budget="108000000",
            runtime="144",
            tmdb_vote_average=8,
            tmdb_vote_count=1000,
            imdb_id="tt3659388",
            tmdb_poster_path="https://img.example/m.jpg",
            last_updated=int(time.time()),
        )

    def test_the_page_renders(self):
        response = self.client.get(f"/movies/details/{self.movie.id}/")
        self.assertEqual(response.status_code, 200)

    def test_no_script_touches_elements_that_are_not_there(self):
        """These lookups returned null and threw, aborting the rest."""
        html = self.client.get(
            f"/movies/details/{self.movie.id}/"
        ).content.decode()
        for missing in [
            "getElementById('watchlist-toggle')",
            "getElementById('watched-toggle')",
            "getElementById('rating-form')",
            "getElementById('review-form')",
            "getElementById('share-container')",
        ]:
            self.assertNotIn(missing, html, f"{missing} emitted for a visitor")

    def test_signed_in_members_still_get_the_controls(self):
        User = get_user_model()
        User.objects.create_user(username="alice", password="pwd")
        self.client.login(username="alice", password="pwd")
        html = self.client.get(
            f"/movies/details/{self.movie.id}/"
        ).content.decode()
        for present in [
            "getElementById('watchlist-toggle')",
            "getElementById('watched-toggle')",
            "getElementById('share-container')",
        ]:
            self.assertIn(present, html)


@override_settings(ROOT_URLCONF="moviebuff.urls")
class PublicUserDataTests(TestCase):
    """This is one member's catalogue, so a visitor sees the entry too."""

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="alice", password="pwd")
        self.movie = Movie.objects.create(
            tmdb_id=1,
            title="The Martian",
            overview="Stranded.",
            release_date="2015-10-02",
            original_language="en",
            budget="108000000",
            runtime="144",
            tmdb_vote_average=8,
            tmdb_vote_count=1000,
            imdb_id="tt3659388",
            tmdb_poster_path="https://img.example/m.jpg",
            last_updated=int(time.time()),
        )

    def _watch(self, **kwargs):
        return Watched.objects.create(
            user=self.owner,
            movie=self.movie,
            watched_date=timezone.now(),
            **kwargs,
        )

    def _page(self):
        return self.client.get(f"/movies/details/{self.movie.id}/")

    def test_visitor_sees_the_watched_date_and_rewatch(self):
        self._watch(rewatch=True)
        response = self._page()
        self.assertContains(response, "Watched Date:")
        self.assertContains(response, "<strong>Re-watch:</strong> Y", html=False)

    def _user_data_block(self):
        html = self._page().content.decode()
        start = html.index("User Data")
        return html[start:html.index("</section>", start)]

    def test_visitor_sees_the_rating(self):
        self._watch(rating=4.0)
        self.assertContains(self._page(), "4.0/5")
        # Four filled stars, one empty — counted inside the block, since the
        # reviews list elsewhere on the page draws stars of its own.
        block = self._user_data_block()
        self.assertEqual(block.count("bi-star-fill"), 4)
        self.assertEqual(block.count("bi-star\""), 1)

    def test_visitor_sees_the_review(self):
        self._watch(rating=5.0, review="Loved it.")
        self.assertContains(self._page(), "Loved it.")

    def test_visitor_gets_no_edit_controls(self):
        self._watch(rating=4.0)
        html = self._page().content.decode()
        for control in [
            'id="rating-form"',
            'id="review-form"',
            'id="watched-toggle"',
            'id="watchlist-toggle"',
            'id="rewatch-check"',
            'id="share-container"',
        ]:
            self.assertNotIn(control, html, f"{control} offered to a visitor")

    def test_visitor_sees_not_rated_when_unrated(self):
        self._watch()
        self.assertContains(self._page(), "Not rated")

    def test_unwatched_movie_shows_no_entry_facts(self):
        response = self._page()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Watched Date:")

    def test_watchlist_membership_stays_private(self):
        """A plan to watch is not a record; visitors should not see it."""
        from movies.models import Watchlist

        Watchlist.objects.create(user=self.owner, movie=self.movie)
        self.assertNotContains(self._page(), "Remove from Watchlist")

    def test_the_owner_still_gets_the_controls(self):
        self._watch(rating=4.0)
        self.client.login(username="alice", password="pwd")
        html = self._page().content.decode()
        for control in [
            'id="rating-form"',
            'id="review-form"',
            'id="watched-toggle"',
            'id="rewatch-check"',
        ]:
            self.assertIn(control, html)
