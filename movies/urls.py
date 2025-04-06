from django.urls import path
from . import views

urlpatterns = [
    path('search/', views.search_movies, name='search_movies'),
    path('watched/add/<int:movie_id>/', views.add_to_watched, name='add_to_watched'),
    path('watchlist/add/<int:movie_id>/', views.add_to_watchlist, name='add_to_watchlist'),
    path('watched/remove/<int:movie_id>/', views.remove_from_watched, name='remove_from_watched'), 
    path('watchlist/remove/<int:movie_id>/', views.remove_from_watchlist, name='remove_from_watchlist'), 
    path('details/<int:movie_id>/', views.movie_details, name='movie_details'),
    path('search/tmdb/<int:tmdb_id>/', views.handle_tmdb_redirect, name='handle_movie_redirect'),
]