# Chess Arena V2

FastAPI rewrite of Chess Arena.

V2 separates the chess platform into clear product modes:

- General games: normal wallet-free chess.
- Challenges: funded head-to-head games with escrow settlement.
- Tournaments: organizer-created events with optional prizes.

## Local Development

```bash
make dev
make test
make lint
make format
```

The first milestone is the backend foundation: FastAPI boot, configuration,
health endpoints, test setup, linting, local infrastructure, core chess domain
logic, and database migrations.
