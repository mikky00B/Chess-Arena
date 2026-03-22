from django.contrib import admin
from .models import (
    Profile,
    Game,
    Move,
    SecurityEvent,
    Tournament,
    TournamentParticipant,
    TournamentInvite,
    TournamentMatch,
    TournamentReviewDecision,
    TournamentPayout,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "rating",
        "ethereum_address",
    )
    search_fields = (
        "user__username",
        "user__email",
        "ethereum_address",
    )
    list_filter = ("rating",)
    ordering = ("-rating",)


class MoveInline(admin.TabularInline):
    model = Move
    extra = 0
    readonly_fields = ("move_san", "move_number", "think_time_seconds", "timestamp")
    can_delete = False
    ordering = ("move_number",)


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "white_player",
        "black_player",
        "is_active",
        "winner",
        "bet_amount",
        "payout_claimed",
        "created_at",
    )
    list_filter = (
        "is_active",
        "payout_claimed",
        "created_at",
    )
    search_fields = (
        "white_player__username",
        "black_player__username",
        "winner__username",
        "deposit_tx_hash",
        "claim_tx_hash",
    )
    ordering = ("-created_at",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "last_move_timestamp",
        "deposit_tx_hash",
        "claim_tx_hash",
        "signature_v",
        "signature_r",
        "signature_s",
    )
    fieldsets = (
        (
            "Players",
            {
                "fields": (
                    "white_player",
                    "black_player",
                )
            },
        ),
        (
            "Game State",
            {
                "fields": (
                    "current_fen",
                    "is_active",
                    "winner",
                )
            },
        ),
        (
            "Time Control",
            {
                "fields": (
                    "white_time",
                    "black_time",
                    "last_move_timestamp",
                )
            },
        ),
        (
            "Blockchain & Betting",
            {
                "fields": (
                    "bet_amount",
                    "deposit_tx_hash",
                    "claim_tx_hash",
                    "payout_claimed",
                )
            },
        ),
        (
            "Claim Signatures",
            {
                "fields": (
                    "signature_v",
                    "signature_r",
                    "signature_s",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
    inlines = [MoveInline]


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = (
        "game",
        "move_number",
        "move_san",
        "think_time_seconds",
        "timestamp",
    )
    list_filter = ("timestamp",)
    search_fields = (
        "game__id",
        "move_san",
    )
    ordering = ("game", "move_number")


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "status", "user", "game")
    list_filter = ("event_type", "status", "created_at")
    search_fields = ("event_type", "status", "user__username", "game__id")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "creator", "format", "status", "entry_fee_eth", "created_at")
    list_filter = ("status", "format", "invite_only", "review_required")
    search_fields = ("name", "creator__username")
    ordering = ("-created_at",)


@admin.register(TournamentParticipant)
class TournamentParticipantAdmin(admin.ModelAdmin):
    list_display = ("tournament", "user", "status", "deposit_verified", "points")
    list_filter = ("status", "deposit_verified")
    search_fields = ("tournament__name", "user__username")


@admin.register(TournamentInvite)
class TournamentInviteAdmin(admin.ModelAdmin):
    list_display = ("tournament", "invitee", "status", "expires_at", "created_at")
    list_filter = ("status",)
    search_fields = ("tournament__name", "invitee__username", "token")


@admin.register(TournamentMatch)
class TournamentMatchAdmin(admin.ModelAdmin):
    list_display = (
        "tournament",
        "round_number",
        "board_number",
        "game_index",
        "status",
        "result",
        "suspicion_score",
    )
    list_filter = ("status", "review_status", "requires_manual_review")
    search_fields = ("tournament__name",)


@admin.register(TournamentReviewDecision)
class TournamentReviewDecisionAdmin(admin.ModelAdmin):
    list_display = ("tournament", "scope", "decision", "reviewer", "finalized_at")
    list_filter = ("scope", "decision")
    search_fields = ("tournament__name", "reviewer__username")


@admin.register(TournamentPayout)
class TournamentPayoutAdmin(admin.ModelAdmin):
    list_display = ("tournament", "rank", "participant", "gross_amount", "net_amount", "status")
    list_filter = ("status",)
    search_fields = ("tournament__name", "participant__user__username")
