from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from fedi.models import FediActivity
from fedi.vocab import PUBLIC
from tv.models import TvSeason, TvShelf, TvShow


@override_settings(
    ACTIVITYPUB_ENABLED=True,
    ACTIVITYPUB_DOMAIN="https://example.com",
    ROOT_URLCONF="moviebuff.urls",
)
class TvFederationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        profile = self.user.userprofile
        profile.fedi_enabled = True
        profile.save()
        self.show = TvShow.objects.create(
            tmdb_id=1,
            title="Severance",
            tmdb_poster_path="https://img.example/sev.jpg",
        )
        self.season = TvSeason.objects.create(
            show=self.show, season_number=1, name="Season 1"
        )

    def _latest_note(self):
        activity = FediActivity.objects.order_by("-id").first()
        return activity.payload["object"]

    def test_shelving_alone_does_not_post(self):
        TvShelf.objects.create(
            user=self.user, show=self.show, state=TvShelf.WATCHLIST
        )
        self.assertEqual(FediActivity.objects.count(), 0)

    def test_show_rating_posts(self):
        shelf = TvShelf.objects.create(
            user=self.user, show=self.show, state=TvShelf.WATCHING
        )
        shelf.rating = 5.0
        shelf.save()

        note = self._latest_note()
        self.assertIn("I just watched and rated Severance", note["content"])
        self.assertEqual(note["url"], "https://example.com/tv/details/{}/".format(self.show.id))
        self.assertEqual(note["attachment"][0]["url"], "https://img.example/sev.jpg")

    def test_rewatch_rating_says_re_watched(self):
        shelf = TvShelf.objects.create(
            user=self.user, show=self.show, state=TvShelf.WATCHED, rewatch=True
        )
        shelf.rating = 5.0
        shelf.save()

        note = self._latest_note()
        self.assertIn("I just re-watched and rated Severance", note["content"])

    def test_rewatch_alone_does_not_post(self):
        shelf = TvShelf.objects.create(
            user=self.user, show=self.show, state=TvShelf.WATCHING
        )
        shelf.rewatch = True
        shelf.save()
        self.assertEqual(FediActivity.objects.count(), 0)

    def test_season_rating_names_the_season(self):
        shelf = TvShelf.objects.create(
            user=self.user, season=self.season, state=TvShelf.WATCHED
        )
        shelf.rating = 4.0
        shelf.save()

        note = self._latest_note()
        self.assertIn("Severance", note["content"])
        self.assertIn("Season 1", note["content"])
        self.assertIn(
            f"/tv/details/{self.show.id}/season/1/", note["url"]
        )

    def test_review_posts_with_link(self):
        shelf = TvShelf.objects.create(
            user=self.user, show=self.show, state=TvShelf.WATCHED
        )
        shelf.review = "Unsettling and brilliant."
        shelf.save()

        note = self._latest_note()
        self.assertIn("Unsettling and brilliant.", note["content"])
        self.assertIn("Read on MovieBuff", note["content"])

    def test_review_is_escaped(self):
        shelf = TvShelf.objects.create(
            user=self.user, show=self.show, state=TvShelf.WATCHED
        )
        shelf.review = "<script>alert(1)</script>"
        shelf.save()

        note = self._latest_note()
        self.assertNotIn("<script>", note["content"])
        self.assertIn("&lt;script&gt;", note["content"])

    def test_unchanged_rating_does_not_repost(self):
        shelf = TvShelf.objects.create(
            user=self.user, show=self.show, state=TvShelf.WATCHED
        )
        shelf.rating = 5.0
        shelf.save()
        count = FediActivity.objects.count()

        shelf.state = TvShelf.WATCHING
        shelf.save()
        self.assertEqual(FediActivity.objects.count(), count)

    def test_tv_notes_are_quotable(self):
        """TV posts must carry the same interaction policy as movie posts."""
        shelf = TvShelf.objects.create(
            user=self.user, show=self.show, state=TvShelf.WATCHED
        )
        shelf.rating = 5.0
        shelf.save()

        note = self._latest_note()
        policy = note["interactionPolicy"]["canQuote"]
        self.assertIn(PUBLIC, policy["automaticApproval"])

    def test_no_post_when_federation_disabled_for_user(self):
        profile = self.user.userprofile
        profile.fedi_enabled = False
        profile.save()

        shelf = TvShelf.objects.create(
            user=self.user, show=self.show, state=TvShelf.WATCHED
        )
        shelf.rating = 5.0
        shelf.save()
        self.assertEqual(FediActivity.objects.count(), 0)
