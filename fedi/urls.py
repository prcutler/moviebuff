from django.urls import path

from . import views


urlpatterns = [
    path(".well-known/webfinger", views.webfinger, name="webfinger"),
    path("users/<str:username>", views.actor, name="actor"),
    path("users/<str:username>/outbox", views.outbox, name="outbox"),
    path("users/<str:username>/followers", views.followers, name="followers"),
    path("users/<str:username>/inbox", views.inbox, name="inbox"),
]

