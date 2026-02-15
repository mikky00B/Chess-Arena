from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    rating = models.IntegerField(default=1200)
    ethereum_address = models.CharField(
        max_length=42, blank=True, null=True, unique=True
    )

    def __str__(self):
        return f"{self.user.username} ({self.rating})"


class Game(models.Model):
    white_player = models.ForeignKey(
        User, related_name="games_white", on_delete=models.SET_NULL, null=True
    )
    black_player = models.ForeignKey(
        User,
        related_name="games_black",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    current_fen = models.CharField(
        max_length=255,
        default="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    )

    is_active = models.BooleanField(default=True)
    winner = models.ForeignKey(
        User, related_name="wins", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    white_time = models.FloatField(default=600.0)
    black_time = models.FloatField(default=600.0)
    last_move_timestamp = models.DateTimeField(null=True, blank=True)

    bet_amount = models.DecimalField(
        max_digits=20, decimal_places=18, default=0, help_text="Bet amount in ETH"
    )
    deposit_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    claim_tx_hash = models.CharField(max_length=66, blank=True, null=True)

    signature_v = models.IntegerField(null=True, blank=True)
    signature_r = models.CharField(max_length=66, blank=True, null=True)
    signature_s = models.CharField(max_length=66, blank=True, null=True)

    payout_claimed = models.BooleanField(default=False)

    draw_offered_by = models.ForeignKey(
        User,
        related_name="draw_offers",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    is_private = models.BooleanField(default=False)
    private_link_code = models.CharField(
        max_length=32, blank=True, null=True, unique=True
    )

    def __str__(self):
        return f"Game {self.id}: {self.white_player} vs {self.black_player}"

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "black_player"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["private_link_code"]),
        ]


class Move(models.Model):
    game = models.ForeignKey(Game, related_name="moves", on_delete=models.CASCADE)
    move_san = models.CharField(max_length=10)
    move_number = models.PositiveIntegerField()
    think_time_seconds = models.FloatField(default=0.0)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["move_number"]
        indexes = [
            models.Index(fields=["game", "move_number"]),
        ]


class SecurityEvent(models.Model):
    EVENT_CHOICES = [
        ("signature_generated", "signature_generated"),
        ("signature_generation_failed", "signature_generation_failed"),
        ("payout_marked_claimed", "payout_marked_claimed"),
        ("payout_mark_failed", "payout_mark_failed"),
        ("deposit_verified", "deposit_verified"),
        ("deposit_verify_failed", "deposit_verify_failed"),
    ]

    event_type = models.CharField(max_length=64, choices=EVENT_CHOICES)
    status = models.CharField(max_length=16, default="ok")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    game = models.ForeignKey(Game, on_delete=models.SET_NULL, null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["event_type", "created_at"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type} ({self.status})"
