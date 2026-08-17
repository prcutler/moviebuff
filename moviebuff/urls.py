"""moviebuff URL Configuration"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from moviebuff import search as search_views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("users.urls")),
    # One search across the whole catalogue: movies and shows together.
    path("search/", search_views.search, name="search"),
    path("movies/", include("movies.urls")),
    path("tv/", include("tv.urls")),
]
urlpatterns.append(path("", include("fedi.urls")))

