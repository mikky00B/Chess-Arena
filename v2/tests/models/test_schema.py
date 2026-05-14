from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.core.database import Base
from app.models import (
    Challenge,
    EscrowDeposit,
    FairPlayReport,
    Game,
    Move,
    Prize,
    PrizeDistribution,
    RatingUpdate,
    SecurityEvent,
    SettlementRequest,
    Tournament,
    TournamentMatch,
    TournamentParticipant,
    TournamentRound,
    User,
)


def test_core_tables_are_registered() -> None:
    assert {
        "users",
        "games",
        "moves",
        "rating_updates",
        "challenges",
        "escrow_deposits",
        "settlement_requests",
        "tournaments",
        "tournament_participants",
        "tournament_rounds",
        "tournament_matches",
        "prizes",
        "prize_distributions",
        "security_events",
        "fair_play_reports",
    }.issubset(Base.metadata.tables)


def test_game_table_uses_string_enums_for_portability() -> None:
    game_columns = Game.__table__.columns

    assert game_columns["status"].type.native_enum is False
    assert game_columns["source_type"].type.native_enum is False
    assert game_columns["turn"].type.native_enum is False


def test_rating_update_is_unique_per_game() -> None:
    constraints = {
        constraint.name
        for constraint in RatingUpdate.__table__.constraints
        if constraint.name is not None
    }

    assert "uq_rating_updates_game_id" in constraints


def test_escrow_deposits_prevent_reused_transactions_and_roles() -> None:
    constraints = {
        constraint.name
        for constraint in EscrowDeposit.__table__.constraints
        if constraint.name is not None
    }

    assert "uq_escrow_deposits_tx_hash" in constraints
    assert "uq_escrow_deposits_challenge_role" in constraints


def test_tournament_participants_are_unique_per_tournament() -> None:
    constraints = {
        constraint.name
        for constraint in TournamentParticipant.__table__.constraints
        if constraint.name is not None
    }

    assert "uq_tournament_participant_user" in constraints


def test_tables_compile_for_postgres() -> None:
    dialect = postgresql.dialect()

    for model in (
        User,
        Game,
        Move,
        RatingUpdate,
        Challenge,
        EscrowDeposit,
        SettlementRequest,
        Tournament,
        TournamentParticipant,
        TournamentRound,
        TournamentMatch,
        Prize,
        PrizeDistribution,
        SecurityEvent,
        FairPlayReport,
    ):
        statement = str(CreateTable(model.__table__).compile(dialect=dialect))
        assert f"CREATE TABLE {model.__tablename__}" in statement
