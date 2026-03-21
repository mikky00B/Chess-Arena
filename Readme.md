# Chesschallenge

Real-time chess platform built with Django + Channels, with optional blockchain escrow settlement.

## Current Features

- Live multiplayer games over WebSockets
- Server-validated chess moves (`python-chess`)
- Server-managed clocks and move timing
- Public and private game creation/join flows
- User profiles with ratings and Ethereum address support
- Daily puzzle page (Chess.com puzzle integration)
- Blockchain game flow:
  - Deposit verification
  - Judge signature generation for settlement
  - Payout claim tracking
- Tournament system:
  - Create/invite/join tournaments
  - Deposit verification and tournament locking
  - Start and auto-generate matches
  - Report results, review flags, finalize/cancel
  - Supported formats: round robin, swiss, single elimination, double elimination (basic)
- Ops endpoints:
  - Liveness/readiness checks
  - Network info
  - Fairplay report endpoint

## Stack

- Backend: Django 5, Django Channels, Daphne
- Realtime: Redis channel layer
- Chess engine: `python-chess`
- Database: SQLite (dev), PostgreSQL-ready
- Blockchain integration: `web3`, `eth-account`
- Frontend: Django templates

## Key Routes

- Web:
  - `/` lobby
  - `/create/`, `/join/<game_id>/`, `/join-private/<link_code>/`
  - `/game/<game_id>/`
  - `/tournaments/create/`, `/tournaments/<tournament_id>/`
  - `/daily-puzzle/`
- APIs:
  - `/api/verify-deposit/<game_id>/`
  - `/api/get-signature/<game_id>/`
  - `/api/mark-payout/<game_id>/`
  - `/api/tournaments/...`
  - `/health/live/`, `/health/ready/`

## Local Run

```bash
cd djangoChess
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Notes

- This is a demo/portfolio project and is not production-hardened.
- Smart contract code is in `chess_blockchain/`.
