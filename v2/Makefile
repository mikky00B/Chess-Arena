.PHONY: dev test lint format migrate contracts-test

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

test:
	pytest

lint:
	ruff check app tests
	mypy app

format:
	ruff format app tests
	ruff check --fix app tests

migrate:
	alembic upgrade head

contracts-test:
	pytest tests/contracts

