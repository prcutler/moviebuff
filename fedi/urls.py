from django.urls import path

from . import views


urlpatterns = [
    path(".well-known/webfinger", views.webfinger, name="webfinger"),
    path("users/<str:username>", views.actor, name="actor"),
]

