"""create core game tables

Revision ID: 20260506_0001
Revises:
Create Date: 2026-05-06 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260506_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "games",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("white_player_id", sa.Uuid(), nullable=False),
        sa.Column("black_player_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Enum(native_enum=False, length=32), nullable=False),
        sa.Column("current_fen", sa.Text(), nullable=False),
        sa.Column("time_control_initial_seconds", sa.Integer(), nullable=False),
        sa.Column("time_control_increment_seconds", sa.Integer(), nullable=False),
        sa.Column("white_time_seconds", sa.Integer(), nullable=False),
        sa.Column("black_time_seconds", sa.Integer(), nullable=False),
        sa.Column("last_clock_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("turn", sa.Enum(native_enum=False, length=8), nullable=False),
        sa.Column("rated", sa.Boolean(), nullable=False),
        sa.Column("result", sa.Enum(native_enum=False, length=16), nullable=True),
        sa.Column("result_reason", sa.Enum(native_enum=False, length=32), nullable=True),
        sa.Column("winner_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.Enum(native_enum=False, length=32), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.Column("draw_offered_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["black_player_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["draw_offered_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["white_player_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["winner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_games_black_player_id"), "games", ["black_player_id"], unique=False)
    op.create_index(op.f("ix_games_source_id"), "games", ["source_id"], unique=False)
    op.create_index(op.f("ix_games_source_type"), "games", ["source_type"], unique=False)
    op.create_index(op.f("ix_games_status"), "games", ["status"], unique=False)
    op.create_index(op.f("ix_games_white_player_id"), "games", ["white_player_id"], unique=False)

    op.create_table(
        "moves",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("move_number", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("color", sa.Enum(native_enum=False, length=8), nullable=False),
        sa.Column("uci", sa.String(length=8), nullable=False),
        sa.Column("san", sa.String(length=32), nullable=False),
        sa.Column("fen_after", sa.Text(), nullable=False),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("white_time_seconds", sa.Integer(), nullable=False),
        sa.Column("black_time_seconds", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["player_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_moves_game_id"), "moves", ["game_id"], unique=False)
    op.create_index(op.f("ix_moves_player_id"), "moves", ["player_id"], unique=False)

    op.create_table(
        "rating_updates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("white_player_id", sa.Uuid(), nullable=False),
        sa.Column("black_player_id", sa.Uuid(), nullable=False),
        sa.Column("white_rating_before", sa.Integer(), nullable=False),
        sa.Column("black_rating_before", sa.Integer(), nullable=False),
        sa.Column("white_rating_after", sa.Integer(), nullable=False),
        sa.Column("black_rating_after", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["black_player_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["white_player_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", name="uq_rating_updates_game_id"),
    )


def downgrade() -> None:
    op.drop_table("rating_updates")
    op.drop_index(op.f("ix_moves_player_id"), table_name="moves")
    op.drop_index(op.f("ix_moves_game_id"), table_name="moves")
    op.drop_table("moves")
    op.drop_index(op.f("ix_games_white_player_id"), table_name="games")
    op.drop_index(op.f("ix_games_status"), table_name="games")
    op.drop_index(op.f("ix_games_source_type"), table_name="games")
    op.drop_index(op.f("ix_games_source_id"), table_name="games")
    op.drop_index(op.f("ix_games_black_player_id"), table_name="games")
    op.drop_table("games")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
