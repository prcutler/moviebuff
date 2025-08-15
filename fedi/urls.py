from django.urls import path

from . import views


urlpatterns = [
    path(".well-known/webfinger", views.webfinger, name="webfinger"),
]

