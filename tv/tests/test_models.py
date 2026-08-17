from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from tv.models import TvSeason, TvShelf, TvShow


class TvCatalogueTests(TestCase):
    def setUp(self):
        self.show = TvShow.objects.create(tmdb_id=1, title="Severance")
        self.season = TvSeason.objects.create(
            show=self.show, season_number=1, name="Season 1", episode_count=9
        )

    def test_season_number_unique_per_show(self):
        with self.assertRaises(IntegrityError):
            TvSeason.objects.create(show=self.show, season_number=1)

    def test_same_season_number_allowed_on_another_show(self):
        other = TvShow.objects.create(tmdb_id=2, title="Other")
        TvSeason.objects.create(show=other, season_number=1)
        self.assertEqual(TvSeason.objects.filter(season_number=1).count(), 2)

    def test_tmdb_id_unique(self):
        with self.assertRaises(IntegrityError):
            TvShow.objects.create(tmdb_id=1, title="Duplicate")


class TvShelfConstraintTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        self.show = TvShow.objects.create(tmdb_id=1, title="Severance")
        self.season = TvSeason.objects.create(show=self.show, season_number=1)

    def test_show_only_is_valid(self):
        shelf = TvShelf.objects.create(
            user=self.user, show=self.show, state=TvShelf.WATCHING
        )
        self.assertEqual(shelf.level, "show")
        self.assertEqual(shelf.subject, self.show)

    def test_season_only_is_valid(self):
        shelf = TvShelf.objects.create(
            user=self.user, season=self.season, state=TvShelf.WATCHED
        )
        self.assertEqual(shelf.level, "season")
        self.assertEqual(shelf.subject, self.season)

    def test_neither_subject_is_rejected(self):
        with self.assertRaises(IntegrityError):
            TvShelf.objects.create(user=self.user, state=TvShelf.WATCHLIST)

    def test_both_subjects_is_rejected(self):
        with self.assertRaises(IntegrityError):
            TvShelf.objects.create(
                user=self.user,
                show=self.show,
                season=self.season,
                state=TvShelf.WATCHLIST,
            )

    def test_clean_reports_subject_error_readably(self):
        shelf = TvShelf(user=self.user, state=TvShelf.WATCHLIST)
        with self.assertRaises(ValidationError):
            shelf.clean()

    def test_one_row_per_user_and_show(self):
        TvShelf.objects.create(user=self.user, show=self.show, state=TvShelf.WATCHING)
        with self.assertRaises(IntegrityError):
            TvShelf.objects.create(
                user=self.user, show=self.show, state=TvShelf.WATCHED
            )

    def test_different_users_may_shelf_the_same_show(self):
        User = get_user_model()
        bob = User.objects.create_user(username="bob", password="pwd")
        TvShelf.objects.create(user=self.user, show=self.show, state=TvShelf.WATCHING)
        TvShelf.objects.create(user=bob, show=self.show, state=TvShelf.WATCHED)
        self.assertEqual(TvShelf.objects.filter(show=self.show).count(), 2)

    def test_show_and_season_shelved_independently(self):
        TvShelf.objects.create(user=self.user, show=self.show, state=TvShelf.WATCHING)
        TvShelf.objects.create(
            user=self.user, season=self.season, state=TvShelf.WATCHED
        )
        self.assertEqual(TvShelf.objects.filter(user=self.user).count(), 2)

    def test_rating_out_of_range_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TvShelf.objects.create(
                    user=self.user,
                    show=self.show,
                    state=TvShelf.WATCHED,
                    rating=6.0,
                )
