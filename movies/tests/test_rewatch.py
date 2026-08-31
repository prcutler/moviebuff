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

    def test_a_recorded_rewatch_reads_yes(self):
        Watched.objects.create(
            user=self.user,
            movie=self.movie,
            watched_date=timezone.now(),
            rewatch=True,
        )
        response = self.client.get(f"/movies/details/{self.movie.id}/")
        self.assertContains(response, '<span id="rewatch-status">Y</span>', html=False)

    def test_a_first_viewing_reads_no(self):
        Watched.objects.create(
            user=self.user, movie=self.movie, watched_date=timezone.now()
        )
        response = self.client.get(f"/movies/details/{self.movie.id}/")
        self.assertContains(response, '<span id="rewatch-status">N</span>', html=False)

    def test_the_facts_are_rendered_but_hidden_until_watched(self):
        """Present so script can reveal them without a reload, but not shown."""
        html = self.client.get(
            f"/movies/details/{self.movie.id}/"
        ).content.decode()
        block = html[html.index('id="watched-facts"'):]
        self.assertIn("d-none", block[: block.index(">")])

    def test_the_facts_are_shown_once_watched(self):
        Watched.objects.create(
            user=self.user, movie=self.movie, watched_date=timezone.now()
        )
        html = self.client.get(
            f"/movies/details/{self.movie.id}/"
        ).content.decode()
        block = html[html.index('id="watched-facts"'):]
        self.assertNotIn("d-none", block[: block.index(">")])

    def test_a_visitor_sees_no_facts_block_when_nothing_is_watched(self):
        """A visitor runs no script, so an empty hidden block is pointless."""
        self.client.logout()
        response = self.client.get(f"/movies/details/{self.movie.id}/")
        self.assertNotContains(response, 'id="watched-facts"')

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
        self.assertContains(response, '<span id="rewatch-status">Y</span>', html=False)

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


@override_settings(ROOT_URLCONF="moviebuff.urls")
class EditRewatchOnWatchedMovieTests(TestCase):
    """Correcting the flag on a movie already marked watched."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
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

    def _watch(self, **kwargs):
        return Watched.objects.create(
            user=self.user,
            movie=self.movie,
            watched_date=timezone.now(),
            **kwargs,
        )

    def test_turning_it_on(self):
        self._watch()
        response = self.client.post(
            f"/movies/rewatch/{self.movie.id}/", {"rewatch": "on"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["rewatch"])
        self.assertTrue(Watched.objects.get().rewatch)

    def test_turning_it_off(self):
        self._watch(rewatch=True)
        response = self.client.post(f"/movies/rewatch/{self.movie.id}/", {})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["rewatch"])
        self.assertFalse(Watched.objects.get().rewatch)

    def test_the_checkbox_is_offered_on_an_already_watched_movie(self):
        self._watch(rewatch=True)
        html = self.client.get(
            f"/movies/details/{self.movie.id}/"
        ).content.decode()

        # Scoped to the wrapper: 'd-none' also appears in the script that
        # shows and hides the facts block.
        wrap = html[html.index('id="rewatch-wrap"'):]
        self.assertNotIn("d-none", wrap[: wrap.index(">")])

        box = html[html.index('id="rewatch-check"'):]
        self.assertIn("checked", box[: box.index(">")])

    def test_the_button_reports_whether_an_entry_exists(self):
        """The JS reads data-watched to decide where a change should go."""
        unwatched = self.client.get(f"/movies/details/{self.movie.id}/")
        self.assertContains(unwatched, 'data-watched="false"')

        self._watch()
        watched = self.client.get(f"/movies/details/{self.movie.id}/")
        self.assertContains(watched, 'data-watched="true"')

    def test_it_will_not_invent_an_entry(self):
        """Ticking a box is not a claim to have seen something."""
        response = self.client.post(
            f"/movies/rewatch/{self.movie.id}/", {"rewatch": "on"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Watched.objects.count(), 0)

    def test_it_leaves_the_rating_and_review_alone(self):
        self._watch(rating=4.0, review="Great.")
        self.client.post(f"/movies/rewatch/{self.movie.id}/", {"rewatch": "on"})
        watched = Watched.objects.get()
        self.assertEqual(watched.rating, 4.0)
        self.assertEqual(watched.review, "Great.")
        self.assertTrue(watched.rewatch)

    def test_it_does_not_touch_another_members_entry(self):
        User = get_user_model()
        bob = User.objects.create_user(username="bob", password="pwd")
        Watched.objects.create(
            user=bob, movie=self.movie, watched_date=timezone.now()
        )
        response = self.client.post(
            f"/movies/rewatch/{self.movie.id}/", {"rewatch": "on"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Watched.objects.get(user=bob).rewatch)

    def test_it_requires_login(self):
        self._watch()
        self.client.logout()
        response = self.client.post(
            f"/movies/rewatch/{self.movie.id}/", {"rewatch": "on"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Watched.objects.get().rewatch)

    def test_editing_it_does_not_federate(self):
        from fedi.models import FediActivity

        profile = self.user.userprofile
        profile.fedi_enabled = True
        profile.save()
        self._watch(rating=4.0)
        FediActivity.objects.all().delete()
        with override_settings(
            ACTIVITYPUB_ENABLED=True, ACTIVITYPUB_DOMAIN="https://example.com"
        ):
            self.client.post(
                f"/movies/rewatch/{self.movie.id}/", {"rewatch": "on"}
            )
            self.assertEqual(FediActivity.objects.count(), 0)


@override_settings(ROOT_URLCONF="moviebuff.urls")
class RewatchSurvivesEntryCreationTests(TestCase):
    """Rating and reviewing also create the entry, so they must carry the box.

    Ticking Re-watch on a movie that is not yet watched saves nothing on its
    own — the value rides along with whatever creates the entry. Rating and
    reviewing both get_or_create, so both have to pass it through.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
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

    def test_rating_an_unwatched_movie_keeps_a_ticked_box(self):
        response = self.client.post(
            f"/movies/rating/{self.movie.id}/", {"rating": "4", "rewatch": "on"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["rewatch"])
        watched = Watched.objects.get()
        self.assertEqual(watched.rating, 4.0)
        self.assertTrue(watched.rewatch)

    def test_reviewing_an_unwatched_movie_keeps_a_ticked_box(self):
        response = self.client.post(
            f"/movies/review/{self.movie.id}/",
            {"review": "Great.", "rewatch": "on"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["rewatch"])
        self.assertTrue(Watched.objects.get().rewatch)

    def test_an_empty_value_clears_the_flag(self):
        Watched.objects.create(
            user=self.user,
            movie=self.movie,
            watched_date=timezone.now(),
            rewatch=True,
        )
        self.client.post(
            f"/movies/rating/{self.movie.id}/", {"rating": "4", "rewatch": ""}
        )
        self.assertFalse(Watched.objects.get().rewatch)

    def test_omitting_the_key_leaves_the_flag_alone(self):
        """A caller that never sends it must not clobber what is stored."""
        Watched.objects.create(
            user=self.user,
            movie=self.movie,
            watched_date=timezone.now(),
            rewatch=True,
        )
        self.client.post(f"/movies/rating/{self.movie.id}/", {"rating": "5"})
        watched = Watched.objects.get()
        self.assertEqual(watched.rating, 5.0)
        self.assertTrue(watched.rewatch)

    def test_the_reported_flag_matches_what_was_stored(self):
        """The JS updates the Y/N line from this, so it must be truthful."""
        response = self.client.post(
            f"/movies/rating/{self.movie.id}/", {"rating": "3", "rewatch": "on"}
        )
        self.assertEqual(
            response.json()["rewatch"], Watched.objects.get().rewatch
        )

    def test_the_full_flow_from_the_users_report(self):
        """Add a movie, tick Re-watch, then rate it."""
        # Ticking alone sends nothing while no entry exists.
        self.assertEqual(Watched.objects.count(), 0)
        # Rating carries the box.
        self.client.post(
            f"/movies/rating/{self.movie.id}/", {"rating": "4", "rewatch": "on"}
        )
        watched = Watched.objects.get()
        self.assertTrue(watched.rewatch, "the ticked box was lost")

        # And the page then shows it.
        response = self.client.get(f"/movies/details/{self.movie.id}/")
        self.assertContains(
            response, '<span id="rewatch-status">Y</span>', html=False
        )
