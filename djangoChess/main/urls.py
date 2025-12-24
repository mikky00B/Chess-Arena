from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("game/<int:game_id>/", views.game_detail, name="game_detail"),
    path("", views.lobby, name="lobby"),
    path("create/", views.create_game, name="create_game"),
    path("join/<int:game_id>/", views.join_game, name="join_game"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="main/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("signup/", views.signup, name="signup"),
]
