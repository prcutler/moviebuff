from django.urls import path
from . import views
from .views import logout_view
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(template_name="users/login.html"), name="login"),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('users/<str:username>', views.user_actor, name='user_actor'),
    path('user/<str:username>/', views.user_profile, name='user_profile'),
]
