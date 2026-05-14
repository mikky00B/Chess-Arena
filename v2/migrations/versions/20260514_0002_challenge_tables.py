"""create challenge tables

Revision ID: 20260514_0002
Revises: 20260506_0001
Create Date: 2026-05-14 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260514_0002"
down_revision: str | None = "20260506_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("creator_id", sa.Uuid(), nullable=False),
        sa.Column("opponent_id", sa.Uuid(), nullable=True),
        sa.Column("game_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Enum(native_enum=False, length=32), nullable=False),
        sa.Column("stake_asset_type", sa.Enum(native_enum=False, length=16), nullable=False),
        sa.Column("stake_token_address", sa.String(length=64), nullable=True),
        sa.Column("stake_amount", sa.Numeric(38, 0), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("escrow_contract_address", sa.String(length=64), nullable=False),
        sa.Column("creator_wallet_address", sa.String(length=64), nullable=False),
        sa.Column("opponent_wallet_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("funded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["opponent_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id"),
    )
    op.create_index(op.f("ix_challenges_creator_id"), "challenges", ["creator_id"])
    op.create_index(op.f("ix_challenges_opponent_id"), "challenges", ["opponent_id"])
    op.create_index(op.f("ix_challenges_status"), "challenges", ["status"])

    op.create_table(
        "escrow_deposits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("challenge_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Enum(native_enum=False, length=8), nullable=False),
        sa.Column("wallet_address", sa.String(length=64), nullable=False),
        sa.Column("tx_hash", sa.String(length=80), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("token_address", sa.String(length=64), nullable=True),
        sa.Column("amount", sa.Numeric(38, 0), nullable=False),
        sa.Column("escrow_contract_address", sa.String(length=64), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["challenge_id"], ["challenges.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("challenge_id", "role", name="uq_escrow_deposits_challenge_role"),
        sa.UniqueConstraint("tx_hash", name="uq_escrow_deposits_tx_hash"),
    )
    op.create_index(op.f("ix_escrow_deposits_challenge_id"), "escrow_deposits", ["challenge_id"])
    op.create_index(op.f("ix_escrow_deposits_tx_hash"), "escrow_deposits", ["tx_hash"])
    op.create_index(op.f("ix_escrow_deposits_user_id"), "escrow_deposits", ["user_id"])

    op.create_table(
        "settlement_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.Enum(native_enum=False, length=16), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Enum(native_enum=False, length=16), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("winner_id", sa.Uuid(), nullable=True),
        sa.Column("asset_type", sa.Enum(native_enum=False, length=16), nullable=False),
        sa.Column("token_address", sa.String(length=64), nullable=True),
        sa.Column("amount", sa.Numeric(38, 0), nullable=False),
        sa.Column("recipient_address", sa.String(length=64), nullable=True),
        sa.Column("payload_hash", sa.String(length=66), nullable=False),
        sa.Column("multisig_tx_hash", sa.String(length=80), nullable=True),
        sa.Column("executed_tx_hash", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["winner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payload_hash"),
    )
    op.create_index(op.f("ix_settlement_requests_game_id"), "settlement_requests", ["game_id"])
    op.create_index(op.f("ix_settlement_requests_source_id"), "settlement_requests", ["source_id"])
    op.create_index(
        op.f("ix_settlement_requests_source_type"),
        "settlement_requests",
        ["source_type"],
    )
    op.create_index(op.f("ix_settlement_requests_status"), "settlement_requests", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_settlement_requests_status"), table_name="settlement_requests")
    op.drop_index(op.f("ix_settlement_requests_source_type"), table_name="settlement_requests")
    op.drop_index(op.f("ix_settlement_requests_source_id"), table_name="settlement_requests")
    op.drop_index(op.f("ix_settlement_requests_game_id"), table_name="settlement_requests")
    op.drop_table("settlement_requests")
    op.drop_index(op.f("ix_escrow_deposits_user_id"), table_name="escrow_deposits")
    op.drop_index(op.f("ix_escrow_deposits_tx_hash"), table_name="escrow_deposits")
    op.drop_index(op.f("ix_escrow_deposits_challenge_id"), table_name="escrow_deposits")
    op.drop_table("escrow_deposits")
    op.drop_index(op.f("ix_challenges_status"), table_name="challenges")
    op.drop_index(op.f("ix_challenges_opponent_id"), table_name="challenges")
    op.drop_index(op.f("ix_challenges_creator_id"), table_name="challenges")
    op.drop_table("challenges")
