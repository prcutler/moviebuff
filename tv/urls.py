from django.urls import path

from . import views


urlpatterns = [
    path("search/", views.search_tv, name="tv_search"),
    path(
        "search/tmdb/<int:tmdb_id>/",
        views.handle_tmdb_redirect,
        name="handle_tv_redirect",
    ),
    path("details/<int:show_id>/", views.tv_show_details, name="tv_show_details"),
    path(
        "details/<int:show_id>/season/<int:season_number>/",
        views.tv_season_details,
        name="tv_season_details",
    ),
    # Show-level actions.
    path("state/<int:show_id>/", views.set_state, name="tv_set_state"),
    path("rating/<int:show_id>/", views.update_rating, name="tv_update_rating"),
    path("review/<int:show_id>/", views.submit_review, name="tv_submit_review"),
    path("rewatch/<int:show_id>/", views.set_rewatch, name="tv_set_rewatch"),
    # Season-level actions, same handlers with the season named.
    path(
        "state/<int:show_id>/season/<int:season_number>/",
        views.set_state,
        name="tv_set_season_state",
    ),
    path(
        "rating/<int:show_id>/season/<int:season_number>/",
        views.update_rating,
        name="tv_update_season_rating",
    ),
    path(
        "review/<int:show_id>/season/<int:season_number>/",
        views.submit_review,
        name="tv_submit_season_review",
    ),
    path(
        "rewatch/<int:show_id>/season/<int:season_number>/",
        views.set_rewatch,
        name="tv_set_season_rewatch",
    ),
    path("shelf/<str:state>/", views.view_all_shelf, name="tv_view_all_shelf"),
]
