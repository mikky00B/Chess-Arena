"""
Add these URL patterns to your main urls.py or app urls.py
"""

from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views, blockchain_views, ops_views, tournament_views

urlpatterns = [
    # Existing routes
    path("", views.lobby, name="lobby"),
    path("signup/", views.signup, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("game/<int:game_id>/", views.game_detail, name="game_detail"),
    path("create/", views.create_game, name="create_game"),
    path("daily-puzzle/", views.daily_puzzle_page, name="daily_puzzle_page"),
    path("tournaments/create/", views.tournament_create_page, name="tournament_create_page"),
    path("tournaments/<int:tournament_id>/", views.tournament_detail_page, name="tournament_detail_page"),
    path(
        "tournaments/invite/<str:invite_token>/",
        tournament_views.accept_tournament_invite,
        name="accept_tournament_invite",
    ),
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
    path(
        "api/tournaments/create/",
        tournament_views.create_tournament,
        name="create_tournament",
    ),
    path(
        "api/tournaments/<int:tournament_id>/invite/",
        tournament_views.invite_to_tournament,
        name="invite_to_tournament",
    ),
    path(
        "api/tournaments/<int:tournament_id>/join/",
        tournament_views.join_public_tournament,
        name="join_public_tournament",
    ),
    path(
        "api/tournaments/<int:tournament_id>/respond/",
        tournament_views.respond_tournament_invite,
        name="respond_tournament_invite",
    ),
    path(
        "api/tournaments/<int:tournament_id>/verify-deposit/",
        tournament_views.verify_tournament_deposit,
        name="verify_tournament_deposit",
    ),
    path(
        "api/tournaments/<int:tournament_id>/lock/",
        tournament_views.lock_tournament,
        name="lock_tournament",
    ),
    path(
        "api/tournaments/<int:tournament_id>/start/",
        tournament_views.start_tournament,
        name="start_tournament",
    ),
    path(
        "api/tournaments/<int:tournament_id>/matches/<int:match_id>/report/",
        tournament_views.report_tournament_match,
        name="report_tournament_match",
    ),
    path(
        "api/tournaments/<int:tournament_id>/review/",
        tournament_views.review_tournament,
        name="review_tournament",
    ),
    path(
        "api/tournaments/<int:tournament_id>/finalize/",
        tournament_views.finalize_tournament,
        name="finalize_tournament",
    ),
    path(
        "api/tournaments/<int:tournament_id>/cancel/",
        tournament_views.cancel_tournament,
        name="cancel_tournament",
    ),
]
