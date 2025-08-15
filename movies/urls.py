from django.urls import path
from . import views

urlpatterns = [
    path('search/', views.search_movies, name='search_movies'),
    path('watchlist/toggle/<int:movie_id>/', views.toggle_watchlist, name='toggle_watchlist'),
    path('watched/toggle/<int:movie_id>/', views.toggle_watched, name='toggle_watched'),
    path('watched/add/<int:movie_id>/', views.add_to_watched, name='add_to_watched'),
    path('watchlist/add/<int:movie_id>/', views.add_to_watchlist, name='add_to_watchlist'),
    path('watched/remove/<int:movie_id>/', views.remove_from_watched, name='remove_from_watched'),
    path('watchlist/remove/<int:movie_id>/', views.remove_from_watchlist, name='remove_from_watchlist'),
    path('details/<int:movie_id>/', views.movie_details, name='movie_details'),
    path('search/tmdb/<int:tmdb_id>/', views.handle_tmdb_redirect, name='handle_movie_redirect'),
    path('custom_watchlist/remove/<int:movie_id>/<int:watchlist_id>/', views.remove_from_custom_watchlist, name='remove_from_custom_watchlist'),
    path('custom_watchlist/delete/<int:watchlist_id>/', views.delete_custom_watchlist, name='delete_custom_watchlist'),
    path('watched/all/', views.view_all_watched, name='view_all_watched'),
    path('watchlist/all/', views.view_all_watchlist, name='view_all_watchlist'),
    path('custom_watchlist/<int:watchlist_id>/', views.view_custom_watchlist, name='view_custom_watchlist'),
]