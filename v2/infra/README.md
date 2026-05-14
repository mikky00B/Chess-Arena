# Infrastructure

Deployment and operational configuration for V2.

## Runtime Settings

V2 reads settings from `CHESS_ARENA_*` environment variables.

Required production settings:

- `CHESS_ARENA_ENV=production`
- `CHESS_ARENA_DATABASE_URL`
- `CHESS_ARENA_REDIS_URL`
- `CHESS_ARENA_SECRET_KEY`
- `CHESS_ARENA_CORS_ALLOWED_ORIGINS`

Production startup fails fast when local/default database credentials, localhost Redis, wildcard
CORS, or a weak secret key are configured.

## Health Checks

- `GET /health/live` returns process liveness.
- `GET /health/ready` returns app, database, and Redis readiness. Set
  `CHESS_ARENA_STRICT_HEALTH_CHECKS=true` in deployed environments to perform live dependency
  probes.

## Security And Observability

- Every HTTP response includes `x-request-id`.
- Access logs are emitted as JSON with request ID, method, path, status, duration, and client IP.
- CORS is restricted to configured origins.
- Mutating game, matchmaking, challenge, tournament, settlement, and fair-play endpoints are
  protected by rate limiting.
- Security-sensitive operations write `security_events` records.
- Fair-play reports start in `fair_play_reports` for later review tooling and engine analysis.

## Docker Production Profile

Run the production profile with explicit environment values:

```powershell
docker compose --profile production up --build api-prod
```

For local development, keep using:

```powershell
docker compose up --build api
```
