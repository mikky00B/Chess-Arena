"""create security ops tables

Revision ID: 20260514_0004
Revises: 20260514_0003
Create Date: 2026-05-14 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260514_0004"
down_revision: str | None = "20260514_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "security_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.Enum(native_enum=False, length=16), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_security_events_created_at"), "security_events", ["created_at"])
    op.create_index(op.f("ix_security_events_event_type"), "security_events", ["event_type"])
    op.create_index(op.f("ix_security_events_request_id"), "security_events", ["request_id"])
    op.create_index(
        op.f("ix_security_events_resource_id"),
        "security_events",
        ["resource_id"],
    )
    op.create_index(
        op.f("ix_security_events_resource_type"),
        "security_events",
        ["resource_type"],
    )
    op.create_index(op.f("ix_security_events_severity"), "security_events", ["severity"])
    op.create_index(op.f("ix_security_events_user_id"), "security_events", ["user_id"])

    op.create_table(
        "fair_play_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("reporter_id", sa.Uuid(), nullable=True),
        sa.Column("accused_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=128), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum(native_enum=False, length=16), nullable=False),
        sa.Column("engine_match_percent", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["accused_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_fair_play_reports_accused_user_id"),
        "fair_play_reports",
        ["accused_user_id"],
    )
    op.create_index(
        op.f("ix_fair_play_reports_created_at"),
        "fair_play_reports",
        ["created_at"],
    )
    op.create_index(op.f("ix_fair_play_reports_game_id"), "fair_play_reports", ["game_id"])
    op.create_index(op.f("ix_fair_play_reports_reason"), "fair_play_reports", ["reason"])
    op.create_index(
        op.f("ix_fair_play_reports_reporter_id"),
        "fair_play_reports",
        ["reporter_id"],
    )
    op.create_index(op.f("ix_fair_play_reports_status"), "fair_play_reports", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_fair_play_reports_status"), table_name="fair_play_reports")
    op.drop_index(op.f("ix_fair_play_reports_reporter_id"), table_name="fair_play_reports")
    op.drop_index(op.f("ix_fair_play_reports_reason"), table_name="fair_play_reports")
    op.drop_index(op.f("ix_fair_play_reports_game_id"), table_name="fair_play_reports")
    op.drop_index(op.f("ix_fair_play_reports_created_at"), table_name="fair_play_reports")
    op.drop_index(op.f("ix_fair_play_reports_accused_user_id"), table_name="fair_play_reports")
    op.drop_table("fair_play_reports")
    op.drop_index(op.f("ix_security_events_user_id"), table_name="security_events")
    op.drop_index(op.f("ix_security_events_severity"), table_name="security_events")
    op.drop_index(op.f("ix_security_events_resource_type"), table_name="security_events")
    op.drop_index(op.f("ix_security_events_resource_id"), table_name="security_events")
    op.drop_index(op.f("ix_security_events_request_id"), table_name="security_events")
    op.drop_index(op.f("ix_security_events_event_type"), table_name="security_events")
    op.drop_index(op.f("ix_security_events_created_at"), table_name="security_events")
    op.drop_table("security_events")
