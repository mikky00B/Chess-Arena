# Chess Arena V2

Chess Arena V2 is the active FastAPI/React rewrite of the original Django chess
application. It is designed as a chess platform first, with optional competitive
and Web3 modes layered on top.

The product is split into three clear modes:

- General games: normal wallet-free chess with matchmaking, private invites,
  clocks, results, and ratings.
- Challenges: funded head-to-head games where escrow must be verified before
  play can start.
- Tournaments: organizer-created events that reuse the core game engine and can
  track prizes or rewards.

The legacy Django app remains in `../djangoChess` while V2 is being promoted to
the repository default branch.

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
To customize local settings, copy `.env.example` to `.env` and edit the values.

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

You can also use the Makefile shortcuts from inside `v2/`:

```powershell
make dev
make test
make lint
make format
make migrate
```

These shortcuts assume `make` is installed and the V2 virtual environment is
active or its `Scripts` directory is on `PATH`. The explicit `.\.venv\Scripts\...`
commands above work without activating the environment.

## Backend Checks

Run the full backend test suite:

```powershell
cd v2
.\.venv\Scripts\python.exe -m pytest
```

Run linting and type checks:

```powershell
.\.venv\Scripts\ruff.exe check app tests migrations
.\.venv\Scripts\mypy.exe app migrations
```

Verify migrations render valid SQL:

```powershell
.\.venv\Scripts\alembic.exe upgrade head --sql
```

Important API surfaces:

- Health: `GET /health/live`, `GET /health/ready`
- Users: `/api/users/...`
- Games: `/api/games/...`
- Matchmaking: `/api/matchmaking/...`
- Challenges: `/api/challenges/...`
- Settlements: `/api/settlements/...`
- Tournaments: `/api/tournaments/...`
- Fair play and ops: `/api/fair-play/...`, `/api/admin/...`
- WebSocket gameplay: `/ws/games/{game_id}`

## Frontend Setup

The V2 frontend lives inside `v2/frontend`. Do not use a top-level `frontend`
folder for V2 development.

```powershell
cd v2\frontend
npm install
```

Start the frontend dev server:

```powershell
npm run dev
```

The frontend will be available at:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

If port `5173` is already occupied, Vite may use `5174`; the local CORS
defaults allow both ports.

Build the frontend:

```powershell
npm run build
```

Preview the production build:

```powershell
npm run preview
```

Run frontend linting:

```powershell
npm run lint
```

## Contract Setup

The V2 contract project lives in `v2/contracts`.

```powershell
cd v2\contracts
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

Run contract tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests
```

Compile the V2 escrow contract:

```powershell
.\.venv\Scripts\mox.exe compile
```

If you already have the legacy `chess_blockchain` virtual environment set up,
you can reuse it from the V2 contracts directory:

```powershell
cd v2\contracts
..\..\chess_blockchain\.venv\Scripts\python.exe -m pytest tests
..\..\chess_blockchain\.venv\Scripts\mox.exe compile
```

## Docker API Stack

To run Postgres, Redis, and the API together:

```powershell
cd v2
docker compose up --build
```

Apply migrations inside the running API container before using database-backed
endpoints:

```powershell
docker compose exec api alembic upgrade head
```

To stop the stack:

```powershell
docker compose down
```

To remove local database volume data:

```powershell
docker compose down -v
```

## Environment

Defaults are development-safe and point at the Docker Compose services:

- Database: `postgresql+asyncpg://chess_arena:chess_arena@localhost:5433/chess_arena`
- Redis: `redis://localhost:6380/0`
- CORS origins: `http://localhost:5173`, `http://127.0.0.1:5173`,
  `http://localhost:5174`, `http://127.0.0.1:5174`, `http://localhost:8001`

Override settings with environment variables or a `.env` file using the
`CHESS_ARENA_` prefix. Common values:

```powershell
$env:CHESS_ARENA_ENV = "development"
$env:CHESS_ARENA_DATABASE_URL = "postgresql+asyncpg://chess_arena:chess_arena@localhost:5433/chess_arena"
$env:CHESS_ARENA_REDIS_URL = "redis://localhost:6380/0"
$env:CHESS_ARENA_CORS_ALLOWED_ORIGINS = '["http://localhost:5173","http://127.0.0.1:5173","http://localhost:5174","http://127.0.0.1:5174","http://localhost:8001"]'
```

Production mode rejects unsafe defaults, including local database credentials,
localhost Redis, wildcard CORS origins, and weak secret keys.

## Generated Files

These should not be committed:

- `v2/.venv/`
- `v2/frontend/node_modules/`
- `v2/frontend/dist/`
- `v2/contracts/.venv/`
- `v2/contracts/.boa_cache/`

If a top-level `frontend/` folder appears with only `node_modules/` or `dist/`,
it is leftover generated output and is not the V2 frontend source.
