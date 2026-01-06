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
    # Players
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

    # Game State
    current_fen = models.CharField(
        max_length=255,
        default="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    )

    # Status
    is_active = models.BooleanField(default=True)
    winner = models.ForeignKey(
        User, related_name="wins", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Time controls
    white_time = models.FloatField(default=600.0)  # 10 minutes in seconds
    black_time = models.FloatField(default=600.0)
    last_move_timestamp = models.DateTimeField(null=True, blank=True)

    # Blockchain integration
    bet_amount = models.DecimalField(
        max_digits=20, decimal_places=18, default=0, help_text="Bet amount in ETH"
    )
    deposit_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    claim_tx_hash = models.CharField(max_length=66, blank=True, null=True)

    # Signatures for claiming (stored after game ends)
    signature_v = models.IntegerField(null=True, blank=True)
    signature_r = models.CharField(max_length=66, blank=True, null=True)
    signature_s = models.CharField(max_length=66, blank=True, null=True)

    # Payout status
    payout_claimed = models.BooleanField(default=False)

    def __str__(self):
        return f"Game {self.id}: {self.white_player} vs {self.black_player}"

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "black_player"]),
            models.Index(fields=["created_at"]),
        ]


class Move(models.Model):
    game = models.ForeignKey(Game, related_name="moves", on_delete=models.CASCADE)
    move_san = models.CharField(max_length=10)
    move_number = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["move_number"]
        indexes = [
            models.Index(fields=["game", "move_number"]),
        ]
