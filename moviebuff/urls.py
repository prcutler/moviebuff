"""moviebuff URL Configuration"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("users.urls")),
    path("movies/", include("movies.urls")),
    path("tv/", include("tv.urls")),
]
urlpatterns.append(path("", include("fedi.urls")))

