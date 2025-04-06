from django.urls import path
from . import views

urlpatterns = [
    path('.well-known/webfinger', views.webfinger, name='webfinger'),
    path('users/<str:username>/follow/', views.follow_user, name='follow_user'),
    path('users/<str:username>/unfollow/', views.unfollow_user, name='unfollow_user'),
    path('users/<str:username>/followers/', views.followers, name='followers'),
    path('users/<str:username>/following/', views.following, name='following'),
    path('users/<str:username>/', views.actor_detail, name='actor_detail'), 
]
