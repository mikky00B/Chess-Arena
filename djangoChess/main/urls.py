"""
Add these URL patterns to your main urls.py or app urls.py
"""

from django.urls import path
from . import views, blockchain_views

urlpatterns = [
    # Existing routes
    path("", views.lobby, name="lobby"),
    path("signup/", views.signup, name="signup"),
    path("signin/", views.signin, name="login"),
    path("game/<int:game_id>/", views.game_detail, name="game_detail"),
    path("create/", views.create_game, name="create_game"),
    path("join/<int:game_id>/", views.join_game, name="join_game"),
    path("lobby-list/", views.lobby_list_partial, name="lobby_list_partial"),
    # Profile and settings
    path("profile/", views.profile_view, name="profile"),
    path("set-address/", views.set_ethereum_address, name="set_ethereum_address"),
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
    ),
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
]
