# Chess Arena

Chess Arena is a real-time chess platform with normal wallet-free play, funded
head-to-head challenges, tournaments, ratings, and optional blockchain escrow
settlement.

This branch is the V2 FastAPI/React rewrite. The previous Django application is
kept in `djangoChess/` and the older contract project is kept in
`chess_blockchain/` for legacy reference.

## V2 Status

V2 is the active codebase and is intended to become the repository default
branch.

Implemented areas include:

- FastAPI backend with typed settings, request context middleware, rate limiting,
  CORS, health checks, and production config validation.
- PostgreSQL and Redis local development stack through Docker Compose.
- SQLAlchemy models and Alembic migrations for users, games, challenges,
  tournaments, ratings, and security operations.
- General chess games with legal move validation, server-side clocks,
  resignation, draw flow, timeout claims, and rating application.
- Matchmaking and private invite flows.
- Funded challenge lifecycle with creator color selection, deposit tracking,
  start gating, and settlement records.
- Tournament service foundation with bracket and participant behavior covered by
  tests.
- WebSocket gameplay through `ws/games/{game_id}`.
- React/Vite frontend in `v2/frontend`.
- Vyper challenge escrow contract in `v2/contracts`.

## Repository Layout

```text
.
|-- v2/                    # Active V2 application
|   |-- app/               # FastAPI API, services, models, core utilities, WS
|   |-- frontend/          # React/Vite client
|   |-- contracts/         # V2 Vyper escrow contract project
|   |-- migrations/        # Alembic migrations
|   |-- tests/             # Backend, service, model, API, WS tests
|   |-- docker-compose.yml # Local Postgres, Redis, and API stack
|   `-- README.md          # V2 setup and verification guide
|-- djangoChess/           # Legacy V1 Django app
|-- chess_blockchain/      # Legacy contract workspace
|-- V2.md                  # Original V2 planning document
`-- Readme.md              # This repository overview
```

## Stack

- Backend: FastAPI, SQLAlchemy, Alembic, Pydantic Settings, Uvicorn
- Realtime: WebSockets and Redis-backed infrastructure
- Chess: `python-chess`
- Database: PostgreSQL for local/dev parity
- Frontend: React 19, Vite, TypeScript, `react-chessboard`, `chess.js`
- Contracts: Vyper and Moccasin
- Tests and quality: pytest, pytest-asyncio, Ruff, mypy, ESLint

## Local Development

Backend setup from the repository root:

```powershell
cd v2
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
docker compose up -d postgres redis
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8001
```

Frontend setup:

```powershell
cd v2\frontend
npm install
npm run dev
```

Local URLs:

- API: `http://localhost:8001`
- API health: `http://localhost:8001/health/live`
- API readiness: `http://localhost:8001/health/ready`
- Frontend: `http://localhost:5173`

See [v2/README.md](v2/README.md) for complete backend, frontend, Docker, and
contract commands.

## Legacy V1

The Django implementation remains available in `djangoChess/` while V2 is being
promoted. It includes the original template-based app, Django Channels gameplay,
tournament views, and older blockchain integration.

V1 should be treated as legacy after V2 becomes the default branch.

## Production Notes

V2 development defaults are local-only. Production mode requires explicit
database, Redis, CORS, and secret configuration.
