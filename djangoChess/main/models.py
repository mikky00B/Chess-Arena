from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    rating = models.IntegerField(default=1200)

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
    # Default FEN is the starting position of a chess game
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

    white_time = models.FloatField(default=600.0)  # 10 minutes in seconds
    black_time = models.FloatField(default=600.0)
    last_move_timestamp = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Game {self.id}: {self.white_player} vs {self.black_player}"


class Move(models.Model):
    game = models.ForeignKey(Game, related_name="moves", on_delete=models.CASCADE)
    move_san = models.CharField(
        max_length=10
    )  # Standard Algebraic Notation like 'e4', 'Nf3'
    move_number = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["move_number"]
