# Escrow Chess Prototype (Demo)

Portfolio project: a real-time chess platform with optional blockchain settlement.

Status: Demonstration project, not production-ready.

## Why This Exists

This project is a systems-design and engineering demo. It showcases:
- Real-time multiplayer game state over WebSockets
- Off-chain authoritative chess logic and timing controls
- On-chain escrow and settlement integration
- End-to-end testing, CI, ops docs, and threat-modeling artifacts

## Critical Flaws (Known and Intentional Tradeoffs)

This repository is intentionally transparent about product viability limits:

1. Centralized adjudication
- A server-side "judge" signs outcomes. This is a trust bottleneck and a single point of failure.

2. Anti-cheat is incomplete
- No strong engine-detection or behavioral modeling pipeline. High-stakes competitive integrity is not solved.

3. UX and cost friction
- Wallet operations, gas fees, and confirmation delays create onboarding and retention risk versus normal chess apps.


## Features

- Real-time multiplayer chess using Django Channels and WebSockets
- Blockchain escrow settlement with Vyper smart contracts
- ELO rating system
- Server-side clock/timer control
- Judge-signed payout claims
- Draw settlement and abandonment handling

## Architecture

### Frontend
- Django templates, Tailwind CSS, Alpine.js, HTMX

### Backend
- Django + Django Channels
- python-chess for move validation
- PostgreSQL for persistence
- Redis for channel layer

### Blockchain
- Vyper contracts for escrow and payout rules
- Web3.py and EIP-191 signatures
- Judge-oracle pattern for off-chain result authorization

## Project Structure

```text
Chesschallenge/
|-- djangoChess/                 # Off-chain real-time game engine
|   |-- main/
|   |   |-- models.py
|   |   |-- views.py
|   |   |-- consumers.py
|   |   |-- blockchain_utils.py
|   |   |-- blockchain_views.py
|   |   |-- signals.py
|   |   `-- templates/main/
|   `-- requirements.txt
|-- chess_blockchain/            # On-chain settlement layer
|   |-- src/chessgame.vy
|   |-- script/
|   |-- moccasin.toml
|   `-- tests/
|-- docker-compose.yml
`-- .github/workflows/ci.yml
```

## Getting Started

```bash
# from repo root
cd djangoChess
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd ../chess_blockchain
pip install moccasin vyper
moccasin install
```

Run migrations and app:

```bash
cd ../djangoChess
python manage.py migrate
python manage.py runserver
```

## How It Works

1. Player A creates a challenge and funds escrow.
2. Player B joins and matches stake.
3. Game runs off-chain in real time.
4. Server determines result.
5. Judge signs settlement payload.
6. Winner (or both players for draw) settles on-chain.

## Testing

```bash
pytest
pytest chess_blockchain/tests -q
python djangoChess/manage.py check
```

## Tech Stack

| Layer | Technology |
|---|---|
| Smart contracts | Vyper |
| Backend | Django, Django Channels |
| Data | PostgreSQL, Redis |
| Blockchain integration | Web3.py, eth-account |
| Frontend | Django templates, Tailwind, Alpine.js, HTMX |
| Chess engine | python-chess |

## Disclaimer

Educational and portfolio software only. Do not treat this as production financial infrastructure.

## License

MIT. See `LICENSE`.
