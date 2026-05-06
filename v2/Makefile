.PHONY: dev test lint format migrate contracts-test

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

test:
	pytest

lint:
	ruff check app tests migrations
	mypy app migrations

format:
	ruff format app tests migrations
	ruff check --fix app tests migrations

migrate:
	alembic upgrade head

contracts-test:
	pytest tests/contracts
