"""
Add these URL patterns to your main urls.py or app urls.py
"""

from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views, blockchain_views, ops_views

urlpatterns = [
    # Existing routes
    path("", views.lobby, name="lobby"),
    path("signup/", views.signup, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("game/<int:game_id>/", views.game_detail, name="game_detail"),
    path("create/", views.create_game, name="create_game"),
    path("join/<int:game_id>/", views.join_game, name="join_game"),
    path("lobby-list/", views.lobby_list_partial, name="lobby_list_partial"),
    # Profile and settings
    path("profile/", views.profile_view, name="profile"),
    path("set-address/", views.set_ethereum_address, name="set_ethereum_address"),
    path(
        "join-private/<str:link_code>/",
        views.join_private_game,
        name="join_private_game",
    ),
    # Blockchain API routes
    path("api/contract-abi/", blockchain_views.get_contract_abi, name="contract_abi"),
    path(
        "api/verify-deposit/<int:game_id>/",
        blockchain_views.verify_deposit,
        name="verify_deposit",
    ),
    path(
        "api/get-signature/<int:game_id>/",
        blockchain_views.get_signature,
        name="get_signature",
    ),  # Make sure this line exists!
    path(
        "api/mark-payout/<int:game_id>/",
        blockchain_views.mark_payout_claimed,
        name="mark_payout_claimed",
    ),
    path(
        "api/challenge-info/<int:game_id>/",
        blockchain_views.get_challenge_info,
        name="challenge_info",
    ),
    path(
        "api/update-address/",
        blockchain_views.update_ethereum_address,
        name="update_ethereum_address",
    ),
    path(
        "api/estimate-gas/<int:game_id>/",
        blockchain_views.estimate_gas,
        name="estimate_gas",
    ),
    path("health/live/", ops_views.health_live, name="health_live"),
    path("health/ready/", ops_views.health_ready, name="health_ready"),
    path("api/network-info/", ops_views.network_info, name="network_info"),
    path(
        "api/fairplay-report/<int:game_id>/",
        ops_views.fairplay_report,
        name="fairplay_report",
    ),
]
