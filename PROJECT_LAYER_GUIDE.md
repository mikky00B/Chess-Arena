# Chesschallenge Layer Guide

This file explains the full system from UI to settlement.

## 1. Product Layer
- Users create chess games with optional ETH stakes.
- A game can be public or private.
- Gameplay is real-time via WebSockets.
- Settlement is done through a Vyper contract using server-authorized signatures.

## 2. Frontend Layer
- Primary game UI: `djangoChess/main/templates/main/board2.html`
- Lobby/profile/auth: Django templates under `djangoChess/main/templates/main/`
- UI behavior:
  - Chessboard interactions send messages to `/ws/chess/<game_id>/`.
  - Blockchain actions call `/chess/api/*` endpoints.
  - Claim/refund buttons become visible when game ends (no refresh required).

## 3. HTTP Application Layer
- Entrypoints are defined in:
  - `djangoChess/djangoChess/urls.py`
  - `djangoChess/main/urls.py`
- Core views:
  - `views.py`: auth, lobby, game creation/join, profile.
  - `blockchain_views.py`: contract ABI, deposit verification, signature retrieval, payout marking.
  - `ops_views.py`: health checks, network info, fair-play report.

## 4. Realtime Layer (WebSocket)
- Consumer: `djangoChess/main/consumers.py`
- Responsibilities:
  - Validates user is authenticated and belongs to the game.
  - Validates move legality and turn ownership using python-chess.
  - Maintains authoritative FEN and clocks server-side.
  - Broadcasts move/chat/game-over events to both players.
  - Returns authoritative FEN on invalid move so UI snaps back immediately.

## 5. Domain/Game Logic Layer
- Chess rules and outcomes: `djangoChess/main/chess_logic.py`
- ELO rating math: `djangoChess/main/utils.py`
- Fair-play timing heuristics: `djangoChess/main/fairplay.py`
  - Uses move think-time telemetry to flag suspicious timing profiles.

## 6. Security/Audit Layer
- Event audit model: `SecurityEvent` in `djangoChess/main/models.py`
- Audit helper: `djangoChess/main/audit.py`
- Security events are written for:
  - deposit verification success/failure
  - signature generation success/failure
  - payout-claim marking success/failure
- Request correlation:
  - `RequestIDMiddleware` adds `X-Request-ID` to responses.

## 7. Persistence Layer
- Models:
  - `Profile`: ELO + wallet mapping.
  - `Game`: players, state, clocks, bet/payout metadata, signatures.
  - `Move`: SAN + sequence + think time.
  - `SecurityEvent`: audit trail for sensitive flows.
- Migrations in `djangoChess/main/migrations/`.

## 8. Signature & Settlement Layer
- Utilities: `djangoChess/main/blockchain_utils.py`
- Signature flow:
  - Contract verifies EIP-191 signature from judge key.
  - Signature payload binds `(game_id, winner_or_draw_marker, contract_address)`.
- Reliability enhancement:
  - `get_signature` in `blockchain_views.py` generates signatures on-demand if missing.

## 9. Smart Contract Layer
- Vyper contract: `chess_blockchain/src/chessgame.vy`
- Core methods:
  - `deposit(game_id)`
  - `claim_winnings(game_id, winner, v, r, s)`
  - `settle_draw(game_id, v, r, s)`
  - `claim_abandonment(game_id)`
- Includes replay protection and timeout path.

## 10. Operations Layer
- Health endpoints:
  - `/chess/health/live/`
  - `/chess/health/ready/`
- Network diagnostics:
  - `/chess/api/network-info/`
- Fair-play report:
  - `/chess/api/fairplay-report/<game_id>/`

## 11. Testing Layer
- Pytest configuration: `pytest.ini`
- App integration tests:
  - `djangoChess/main/test_api_integration.py`
  - `djangoChess/main/test_blockchain.py`
  - `djangoChess/main/test_fairplay.py`
- Contract structural tests:
  - `chess_blockchain/tests/test_chessgame_contract.py`

## 12. Delivery Layer
- CI pipeline:
  - `.github/workflows/ci.yml`
- Local containerized run:
  - `docker-compose.yml`
  - `djangoChess/Dockerfile`

## 13. End-to-End Logic (Single Game)
1. White creates game in lobby.
2. Black joins game.
3. Both connect to WebSocket room; server enforces authorization.
4. Moves are validated server-side; timers are updated server-side.
5. On completion:
   - winner/draw is set in DB
   - ratings are updated
   - signatures are generated now or on-demand at claim time
6. Winner/drawer submits on-chain transaction.
7. Backend verifies claim transaction before setting `payout_claimed=True`.
8. Audit event is recorded.
