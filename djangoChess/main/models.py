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


class Tournament(models.Model):
    STATUS_CHOICES = [
        ("draft", "draft"),
        ("inviting", "inviting"),
        ("locked", "locked"),
        ("in_progress", "in_progress"),
        ("reviewing", "reviewing"),
        ("finalized", "finalized"),
        ("cancelled", "cancelled"),
    ]
    FORMAT_CHOICES = [
        ("round_robin", "round_robin"),
        ("swiss", "swiss"),
        ("single_elim", "single_elim"),
        ("double_elim", "double_elim"),
    ]

    creator = models.ForeignKey(
        User, related_name="tournaments_created", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    format = models.CharField(
        max_length=20, choices=FORMAT_CHOICES, default="round_robin"
    )
    swiss_rounds = models.PositiveIntegerField(default=0)
    games_per_pairing = models.PositiveIntegerField(default=1)
    max_players = models.PositiveIntegerField(default=8)
    min_players = models.PositiveIntegerField(default=2)
    entry_fee_eth = models.DecimalField(max_digits=20, decimal_places=18, default=0)
    total_prize_pool_eth = models.DecimalField(max_digits=20, decimal_places=18, default=0)
    invite_only = models.BooleanField(default=True)
    review_required = models.BooleanField(default=True)
    start_at = models.DateTimeField(null=True, blank=True)
    check_in_deadline = models.DateTimeField(null=True, blank=True)
    review_deadline = models.DateTimeField(null=True, blank=True)
    escrow_contract_address = models.CharField(max_length=42, blank=True, null=True)
    escrow_locked = models.BooleanField(default=False)
    settlement_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    review_completed_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "format"]),
            models.Index(fields=["creator", "created_at"]),
        ]

    def __str__(self):
        return f"Tournament {self.id}: {self.name}"


class TournamentParticipant(models.Model):
    STATUS_CHOICES = [
        ("invited", "invited"),
        ("accepted", "accepted"),
        ("declined", "declined"),
        ("checked_in", "checked_in"),
        ("disqualified", "disqualified"),
        ("withdrawn", "withdrawn"),
    ]

    tournament = models.ForeignKey(
        Tournament, related_name="participants", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        User, related_name="tournament_participations", on_delete=models.CASCADE
    )
    seed = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="invited")
    deposit_verified = models.BooleanField(default=False)
    deposit_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    points = models.FloatField(default=0.0)
    buchholz = models.FloatField(default=0.0)
    sonneborn_berger = models.FloatField(default=0.0)
    wins = models.PositiveIntegerField(default=0)
    draws = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tournament", "user"], name="unique_tournament_participant"
            )
        ]
        indexes = [
            models.Index(fields=["tournament", "status"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.user.username} in Tournament {self.tournament_id}"


class TournamentInvite(models.Model):
    STATUS_CHOICES = [
        ("pending", "pending"),
        ("accepted", "accepted"),
        ("declined", "declined"),
        ("expired", "expired"),
        ("revoked", "revoked"),
    ]

    tournament = models.ForeignKey(
        Tournament, related_name="invites", on_delete=models.CASCADE
    )
    inviter = models.ForeignKey(
        User, related_name="tournament_invites_sent", on_delete=models.CASCADE
    )
    invitee = models.ForeignKey(
        User, related_name="tournament_invites_received", on_delete=models.CASCADE
    )
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tournament", "invitee"], name="unique_tournament_invitee"
            )
        ]
        indexes = [
            models.Index(fields=["tournament", "status"]),
            models.Index(fields=["invitee", "status"]),
        ]

    def __str__(self):
        return f"Invite {self.id}: {self.invitee.username} -> Tournament {self.tournament_id}"


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


class TournamentMatch(models.Model):
    STATUS_CHOICES = [
        ("scheduled", "scheduled"),
        ("active", "active"),
        ("completed", "completed"),
        ("forfeit", "forfeit"),
        ("voided", "voided"),
        ("flagged", "flagged"),
    ]
    RESULT_CHOICES = [
        ("white_win", "white_win"),
        ("black_win", "black_win"),
        ("draw", "draw"),
        ("forfeit_white", "forfeit_white"),
        ("forfeit_black", "forfeit_black"),
    ]
    REVIEW_STATUS_CHOICES = [
        ("pending", "pending"),
        ("approved", "approved"),
        ("rejected", "rejected"),
    ]

    tournament = models.ForeignKey(
        Tournament, related_name="matches", on_delete=models.CASCADE
    )
    game = models.OneToOneField(
        Game,
        related_name="tournament_match",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    white_participant = models.ForeignKey(
        TournamentParticipant,
        related_name="matches_as_white",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    black_participant = models.ForeignKey(
        TournamentParticipant,
        related_name="matches_as_black",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    round_number = models.PositiveIntegerField(default=1)
    board_number = models.PositiveIntegerField(default=1)
    game_index = models.PositiveIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, blank=True, null=True)
    suspicion_score = models.FloatField(default=0.0)
    requires_manual_review = models.BooleanField(default=False)
    review_status = models.CharField(
        max_length=20, choices=REVIEW_STATUS_CHOICES, default="pending"
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tournament", "round_number", "board_number", "game_index"],
                name="unique_tournament_match_slot",
            )
        ]
        indexes = [
            models.Index(fields=["tournament", "round_number"]),
            models.Index(fields=["status", "review_status"]),
        ]

    def __str__(self):
        return f"Tournament {self.tournament_id} R{self.round_number} B{self.board_number} G{self.game_index}"


class TournamentReviewDecision(models.Model):
    SCOPE_CHOICES = [
        ("match", "match"),
        ("participant", "participant"),
        ("tournament", "tournament"),
    ]
    DECISION_CHOICES = [
        ("approved", "approved"),
        ("flagged", "flagged"),
        ("disqualified", "disqualified"),
        ("voided", "voided"),
    ]

    tournament = models.ForeignKey(
        Tournament, related_name="review_decisions", on_delete=models.CASCADE
    )
    reviewer = models.ForeignKey(
        User, related_name="tournament_reviews", on_delete=models.SET_NULL, null=True
    )
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="match")
    match = models.ForeignKey(
        TournamentMatch,
        related_name="review_decisions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    participant = models.ForeignKey(
        TournamentParticipant,
        related_name="review_decisions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES)
    rationale = models.TextField(blank=True)
    finalized_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["tournament", "scope"]),
            models.Index(fields=["decision", "finalized_at"]),
        ]

    def __str__(self):
        return f"Review {self.id}: {self.scope} {self.decision}"


class TournamentPayout(models.Model):
    STATUS_CHOICES = [
        ("pending", "pending"),
        ("approved", "approved"),
        ("paid", "paid"),
        ("withheld", "withheld"),
    ]

    tournament = models.ForeignKey(
        Tournament, related_name="payouts", on_delete=models.CASCADE
    )
    participant = models.ForeignKey(
        TournamentParticipant,
        related_name="payouts",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    rank = models.PositiveIntegerField()
    gross_amount = models.DecimalField(max_digits=20, decimal_places=18, default=0)
    penalty_amount = models.DecimalField(max_digits=20, decimal_places=18, default=0)
    net_amount = models.DecimalField(max_digits=20, decimal_places=18, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    payout_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tournament", "rank"], name="unique_tournament_payout_rank"
            )
        ]
        indexes = [
            models.Index(fields=["tournament", "status"]),
        ]

    def __str__(self):
        return f"Payout {self.id}: Tournament {self.tournament_id} Rank {self.rank}"
