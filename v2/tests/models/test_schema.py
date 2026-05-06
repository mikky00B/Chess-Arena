from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.core.database import Base
from app.models import Game, Move, RatingUpdate, User


def test_core_tables_are_registered() -> None:
    assert {"users", "games", "moves", "rating_updates"}.issubset(Base.metadata.tables)


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


def test_tables_compile_for_postgres() -> None:
    dialect = postgresql.dialect()

    for model in (User, Game, Move, RatingUpdate):
        statement = str(CreateTable(model.__table__).compile(dialect=dialect))
        assert f"CREATE TABLE {model.__tablename__}" in statement
