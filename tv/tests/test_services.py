from unittest.mock import patch

from django.test import TestCase, override_settings

from tv.models import TvSeason, TvShow
from tv.services import get_or_create_show, poster_url, refresh_show

SHOW_PAYLOAD = {
    "name": "Severance",
    "overview": "Work-life balance.",
    "first_air_date": "2022-02-17",
    "status": "Returning Series",
    # TMDB reports this as a list, and often an empty one.
    "episode_run_time": [],
    "original_language": "en",
    "networks": [{"name": "Apple TV"}],
    "genres": [{"name": "Drama"}, {"name": "Mystery"}],
    "poster_path": "/abc.jpg",
    "vote_average": 8.4,
    "vote_count": 3000,
    "seasons": [
        {
            "season_number": 1,
            "name": "Season 1",
            "air_date": "2022-02-17",
            "episode_count": 9,
            "poster_path": "/s1.jpg",
        },
        {
            "season_number": 2,
            "name": "Season 2",
            "air_date": None,
            "episode_count": 10,
            "poster_path": None,
        },
    ],
}


@override_settings(TMDB_API_KEY="test-key")
class RefreshShowTests(TestCase):
    def test_refresh_populates_show_and_seasons(self):
        show = TvShow.objects.create(tmdb_id=95396)
        refresh_show(show, payload=SHOW_PAYLOAD)

        show.refresh_from_db()
        self.assertEqual(show.title, "Severance")
        self.assertEqual(show.status, "Returning Series")
        self.assertEqual(show.networks, ["Apple TV"])
        self.assertEqual(show.genres, ["Drama", "Mystery"])
        self.assertIn("/abc.jpg", show.tmdb_poster_path)
        self.assertIsNotNone(show.last_updated)

        seasons = list(show.seasons.all())
        self.assertEqual([s.season_number for s in seasons], [1, 2])
        self.assertEqual(seasons[0].episode_count, 9)
        self.assertIsNone(seasons[1].air_date)

    def test_empty_episode_run_time_does_not_crash(self):
        show = TvShow.objects.create(tmdb_id=1)
        refresh_show(show, payload=SHOW_PAYLOAD)
        self.assertIsNone(show.episode_runtime)

    def test_episode_run_time_takes_first_value(self):
        payload = dict(SHOW_PAYLOAD, episode_run_time=[45, 60])
        show = TvShow.objects.create(tmdb_id=2)
        refresh_show(show, payload=payload)
        self.assertEqual(show.episode_runtime, 45)

    def test_refresh_is_idempotent_for_seasons(self):
        show = TvShow.objects.create(tmdb_id=3)
        refresh_show(show, payload=SHOW_PAYLOAD)
        refresh_show(show, payload=SHOW_PAYLOAD)
        self.assertEqual(show.seasons.count(), 2)

    def test_season_zero_is_kept(self):
        payload = dict(
            SHOW_PAYLOAD,
            seasons=[{"season_number": 0, "name": "Specials", "episode_count": 3}],
        )
        show = TvShow.objects.create(tmdb_id=4)
        refresh_show(show, payload=payload)
        self.assertTrue(show.seasons.filter(season_number=0).exists())

    @patch("tv.services._connector")
    def test_get_or_create_show_fetches_once(self, mock_connector):
        mock_connector.return_value.get_tv_details.return_value = SHOW_PAYLOAD

        first = get_or_create_show(95396)
        self.assertEqual(first.title, "Severance")
        self.assertEqual(mock_connector.return_value.get_tv_details.call_count, 1)

        # Fresh row: the second call must not hit TMDB again.
        second = get_or_create_show(95396)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(mock_connector.return_value.get_tv_details.call_count, 1)

    @patch("tv.services._connector")
    def test_stale_show_is_refreshed(self, mock_connector):
        mock_connector.return_value.get_tv_details.return_value = SHOW_PAYLOAD
        show = TvShow.objects.create(tmdb_id=95396, title="Stale", last_updated=0)

        get_or_create_show(95396)
        show.refresh_from_db()
        self.assertEqual(show.title, "Severance")
        self.assertEqual(mock_connector.return_value.get_tv_details.call_count, 1)


class PosterUrlTests(TestCase):
    def test_bare_path_is_made_absolute(self):
        self.assertTrue(poster_url("/abc.jpg").startswith("https://image.tmdb.org"))

    def test_absolute_url_is_left_alone(self):
        url = "https://example.com/p.jpg"
        self.assertEqual(poster_url(url), url)

    def test_missing_path_is_empty(self):
        self.assertEqual(poster_url(None), "")
        self.assertEqual(poster_url(""), "")
