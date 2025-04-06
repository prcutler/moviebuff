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