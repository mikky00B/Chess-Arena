# Chess Arena V2

Chess Arena V2 is the active FastAPI/React chess platform. It is designed as a
chess platform first, with optional competitive and Web3 modes layered on top.

The product is split into three clear modes:

- General games: normal wallet-free chess with matchmaking, private invites,
  clocks, results, and ratings.
- Challenges: funded head-to-head games where escrow must be verified before
  play can start.
- Tournaments: organizer-created events that reuse the core game engine and can
  track prizes or rewards.

This repository branch is intentionally V2-focused. The application source lives
in `v2/`.

## Stack

- Backend: FastAPI, SQLAlchemy, Alembic, Pydantic Settings, Uvicorn
- Realtime: WebSockets and Redis-backed infrastructure
- Chess: `python-chess`
- Database: PostgreSQL for local/dev parity
- Frontend: React 19, Vite, TypeScript, `react-chessboard`, `chess.js`
- Contracts: Vyper and Moccasin
- Tests and quality: pytest, pytest-asyncio, Ruff, mypy, ESLint

## Requirements

- Python 3.11+
- Node.js 20+ for the frontend
- Docker Desktop for Postgres and Redis
- Git Bash, WSL, or PowerShell

The commands below use PowerShell because this repo is currently developed on
Windows.

## Backend Setup

From the repository root:

```powershell
cd v2
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

The app has development defaults, so a `.env` file is optional for local setup.
To customize local settings, copy `v2/.env.example` to `v2/.env` and edit the
values.

Start local infrastructure:

```powershell
docker compose up -d postgres redis
```

Run database migrations:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

Start the API:

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8001
```

The API will be available at:

- `http://localhost:8001/health/live`
- `http://localhost:8001/health/ready`

## Frontend Setup

The V2 frontend lives inside `v2/frontend`.

```powershell
cd v2\frontend
npm install
npm run dev
```

The frontend will be available at:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

## Contract Setup

The V2 contract project lives in `v2/contracts`.

```powershell
cd v2\contracts
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\mox.exe compile
```

## Checks

Backend:

```powershell
cd v2
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check app tests migrations
.\.venv\Scripts\mypy.exe app migrations
```

Frontend:

```powershell
cd v2\frontend
npm run build
npm run lint
```

## API Surfaces

- Health: `GET /health/live`, `GET /health/ready`
- Users: `/api/users/...`
- Games: `/api/games/...`
- Matchmaking: `/api/matchmaking/...`
- Challenges: `/api/challenges/...`
- Settlements: `/api/settlements/...`
- Tournaments: `/api/tournaments/...`
- Fair play and ops: `/api/fair-play/...`, `/api/admin/...`
- WebSocket gameplay: `/ws/games/{game_id}`

## Production Notes

Development defaults are local-only. Production mode rejects unsafe defaults,
including local database credentials, localhost Redis, wildcard CORS origins,
and weak secret keys.
