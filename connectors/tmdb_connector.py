import tmdbsimple as tmdb

class TMDbConnector:
    def __init__(self, api_key):
        tmdb.API_KEY = api_key

    def search_movie(self, query):
        search = tmdb.Search()
        response = search.movie(query=query)
        return search.results

    def get_movie_details(self, movie_id):
        movie = tmdb.Movies(movie_id)
        return movie.info()

    def search_tv(self, query):
        search = tmdb.Search()
        search.tv(query=query)
        return search.results

    def get_tv_details(self, tv_id):
        show = tmdb.TV(tv_id)
        return show.info()

    def get_tv_season(self, tv_id, season_number):
        season = tmdb.TV_Seasons(tv_id, season_number)
        return season.info()