"""create tournament tables

Revision ID: 20260514_0003
Revises: 20260514_0002
Create Date: 2026-05-14 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260514_0003"
down_revision: str | None = "20260514_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tournaments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organizer_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("format", sa.Enum(native_enum=False, length=32), nullable=False),
        sa.Column("status", sa.Enum(native_enum=False, length=32), nullable=False),
        sa.Column("max_players", sa.Integer(), nullable=False),
        sa.Column("time_control_initial_seconds", sa.Integer(), nullable=False),
        sa.Column("time_control_increment_seconds", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registration_opens_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registration_closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organizer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tournaments_format"), "tournaments", ["format"])
    op.create_index(op.f("ix_tournaments_organizer_id"), "tournaments", ["organizer_id"])
    op.create_index(op.f("ix_tournaments_status"), "tournaments", ["status"])

    op.create_table(
        "tournament_participants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tournament_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("eliminated", sa.Boolean(), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tournament_id", "user_id", name="uq_tournament_participant_user"),
    )
    op.create_index(
        op.f("ix_tournament_participants_tournament_id"),
        "tournament_participants",
        ["tournament_id"],
    )
    op.create_index(
        op.f("ix_tournament_participants_user_id"),
        "tournament_participants",
        ["user_id"],
    )

    op.create_table(
        "tournament_rounds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tournament_id", sa.Uuid(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tournament_id", "round_number", name="uq_tournament_round_number"),
    )
    op.create_index(
        op.f("ix_tournament_rounds_tournament_id"),
        "tournament_rounds",
        ["tournament_id"],
    )

    op.create_table(
        "prizes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tournament_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("asset_type", sa.Enum(native_enum=False, length=16), nullable=False),
        sa.Column("token_address", sa.String(length=64), nullable=True),
        sa.Column("token_id", sa.String(length=128), nullable=True),
        sa.Column("amount", sa.Numeric(38, 0), nullable=True),
        sa.Column("metadata_uri", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_prizes_tournament_id"), "prizes", ["tournament_id"])

    op.create_table(
        "tournament_matches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tournament_id", sa.Uuid(), nullable=False),
        sa.Column("round_id", sa.Uuid(), nullable=False),
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("white_participant_id", sa.Uuid(), nullable=False),
        sa.Column("black_participant_id", sa.Uuid(), nullable=False),
        sa.Column("winner_participant_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["black_participant_id"], ["tournament_participants.id"]),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["round_id"], ["tournament_rounds.id"]),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"]),
        sa.ForeignKeyConstraint(["white_participant_id"], ["tournament_participants.id"]),
        sa.ForeignKeyConstraint(["winner_participant_id"], ["tournament_participants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id"),
    )
    op.create_index(
        op.f("ix_tournament_matches_round_id"),
        "tournament_matches",
        ["round_id"],
    )
    op.create_index(
        op.f("ix_tournament_matches_tournament_id"),
        "tournament_matches",
        ["tournament_id"],
    )

    op.create_table(
        "prize_distributions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("prize_id", sa.Uuid(), nullable=False),
        sa.Column("tournament_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("tx_hash", sa.String(length=80), nullable=True),
        sa.Column("distributed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["prize_id"], ["prizes.id"]),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_prize_distributions_prize_id"),
        "prize_distributions",
        ["prize_id"],
    )
    op.create_index(
        op.f("ix_prize_distributions_tournament_id"),
        "prize_distributions",
        ["tournament_id"],
    )
    op.create_index(
        op.f("ix_prize_distributions_user_id"),
        "prize_distributions",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_prize_distributions_user_id"), table_name="prize_distributions")
    op.drop_index(op.f("ix_prize_distributions_tournament_id"), table_name="prize_distributions")
    op.drop_index(op.f("ix_prize_distributions_prize_id"), table_name="prize_distributions")
    op.drop_table("prize_distributions")
    op.drop_index(op.f("ix_tournament_matches_tournament_id"), table_name="tournament_matches")
    op.drop_index(op.f("ix_tournament_matches_round_id"), table_name="tournament_matches")
    op.drop_table("tournament_matches")
    op.drop_index(op.f("ix_prizes_tournament_id"), table_name="prizes")
    op.drop_table("prizes")
    op.drop_index(op.f("ix_tournament_rounds_tournament_id"), table_name="tournament_rounds")
    op.drop_table("tournament_rounds")
    op.drop_index(op.f("ix_tournament_participants_user_id"), table_name="tournament_participants")
    op.drop_index(
        op.f("ix_tournament_participants_tournament_id"),
        table_name="tournament_participants",
    )
    op.drop_table("tournament_participants")
    op.drop_index(op.f("ix_tournaments_status"), table_name="tournaments")
    op.drop_index(op.f("ix_tournaments_organizer_id"), table_name="tournaments")
    op.drop_index(op.f("ix_tournaments_format"), table_name="tournaments")
    op.drop_table("tournaments")
