from unittest.mock import patch

from django.test import TestCase, override_settings

from moviebuff.search import _card

MULTI_RESULTS = [
    {
        "media_type": "tv",
        "id": 95396,
        "name": "Severance",
        "first_air_date": "2022-02-17",
        "overview": "Work-life balance.",
        "poster_path": "/sev.jpg",
    },
    {
        "media_type": "movie",
        "id": 5072,
        "title": "Severance",
        "release_date": "2006-05-19",
        "overview": "A team-building weekend.",
        "poster_path": "/mov.jpg",
    },
    # TMDB blends people into multi-search; the catalogue has nowhere to put them.
    {
        "media_type": "person",
        "id": 18891,
        "name": "Joan Severance",
        "poster_path": None,
    },
]


@override_settings(ROOT_URLCONF="moviebuff.urls", TMDB_API_KEY="test-key")
class UnifiedSearchTests(TestCase):
    def test_blank_query_renders_the_form(self):
        response = self.client.get("/search/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Search movies and TV shows")

    @patch("moviebuff.search.TMDbConnector")
    def test_movies_and_shows_appear_together(self, mock_connector):
        mock_connector.return_value.search_multi.return_value = MULTI_RESULTS

        response = self.client.get("/search/?q=severance")
        self.assertEqual(response.status_code, 200)
        # Both kinds present, each labelled.
        self.assertContains(response, "text-bg-info")  # TV badge
        self.assertContains(response, "text-bg-secondary")  # Movie badge
        self.assertContains(response, "/tv/search/tmdb/95396/")
        self.assertContains(response, "/movies/search/tmdb/5072/")

    @patch("moviebuff.search.TMDbConnector")
    def test_people_are_dropped(self, mock_connector):
        mock_connector.return_value.search_multi.return_value = MULTI_RESULTS

        response = self.client.get("/search/?q=severance")
        self.assertNotContains(response, "Joan Severance")
        self.assertContains(response, "2 results")

    @patch("moviebuff.search.TMDbConnector")
    def test_movie_filter_uses_the_movie_endpoint(self, mock_connector):
        mock_connector.return_value.search_movie.return_value = [
            {"id": 5072, "title": "Severance", "release_date": "2006-05-19"}
        ]

        response = self.client.get("/search/?q=severance&kind=movie")
        self.assertEqual(response.status_code, 200)
        mock_connector.return_value.search_movie.assert_called_once_with("severance")
        mock_connector.return_value.search_multi.assert_not_called()
        self.assertContains(response, "/movies/search/tmdb/5072/")

    @patch("moviebuff.search.TMDbConnector")
    def test_tv_filter_uses_the_tv_endpoint(self, mock_connector):
        mock_connector.return_value.search_tv.return_value = [
            {"id": 95396, "name": "Severance", "first_air_date": "2022-02-17"}
        ]

        response = self.client.get("/search/?q=severance&kind=tv")
        mock_connector.return_value.search_tv.assert_called_once_with("severance")
        mock_connector.return_value.search_multi.assert_not_called()
        self.assertContains(response, "/tv/search/tmdb/95396/")

    @patch("moviebuff.search.TMDbConnector")
    def test_unknown_kind_falls_back_to_everything(self, mock_connector):
        mock_connector.return_value.search_multi.return_value = MULTI_RESULTS

        response = self.client.get("/search/?q=severance&kind=nonsense")
        self.assertEqual(response.status_code, 200)
        mock_connector.return_value.search_multi.assert_called_once()

    @patch("moviebuff.search.TMDbConnector")
    def test_no_results_is_reported(self, mock_connector):
        mock_connector.return_value.search_multi.return_value = []

        response = self.client.get("/search/?q=zzzz")
        self.assertContains(response, "No results")

    @patch("moviebuff.search.TMDbConnector")
    def test_whitespace_only_query_is_treated_as_blank(self, mock_connector):
        response = self.client.get("/search/?q=%20%20")
        self.assertEqual(response.status_code, 200)
        mock_connector.return_value.search_multi.assert_not_called()


class CardNormalisationTests(TestCase):
    def test_tv_uses_name_and_first_air_date(self):
        card = _card(MULTI_RESULTS[0])
        self.assertEqual(card["kind"], "tv")
        self.assertEqual(card["title"], "Severance")
        self.assertEqual(card["year"], "2022")

    def test_movie_uses_title_and_release_date(self):
        card = _card(MULTI_RESULTS[1])
        self.assertEqual(card["kind"], "movie")
        self.assertEqual(card["title"], "Severance")
        self.assertEqual(card["year"], "2006")

    def test_missing_date_yields_empty_year(self):
        card = _card({"media_type": "movie", "id": 1, "title": "Untitled"})
        self.assertEqual(card["year"], "")

    def test_missing_poster_yields_empty_url(self):
        card = _card({"media_type": "movie", "id": 1, "title": "X"})
        self.assertEqual(card["poster_url"], "")


@override_settings(ROOT_URLCONF="moviebuff.urls")
class LegacySearchUrlTests(TestCase):
    def test_movie_search_url_redirects(self):
        response = self.client.get("/movies/search/?q=severance")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/search/", response["Location"])
        self.assertIn("kind=movie", response["Location"])
        self.assertIn("q=severance", response["Location"])
