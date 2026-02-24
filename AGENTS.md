# Instruções do projeto — api-ta-liso-app

## Convenções

### Routes são thin controllers
Routes only process the payload and return the response. All business logic lives in services.
The pattern used: service raises ValueError (bad input) or LookupError (not found) or returns None (not found); router maps to HTTP exceptions.
See categories router as the canonical example.

### Business rules + tests + BDD
Whenever a new business rule is added to the API:
1. Implement the rule in the router/service
2. Add a test scenario (tests/api/ or tests/unit/)
3. Update docs/ta-liso-BDD.md with the corresponding Gherkin scenario

This was explicitly requested by the user and must always be followed.

## Stack
- FastAPI + SQLAlchemy 2.0 async (asyncpg in prod, aiosqlite in tests)
- Pydantic v2 + pydantic-settings (SettingsConfigDict, not ConfigDict)
- Alembic (psycopg2 sync URL for migrations, asyncpg for app)
- AWS SES via boto3 for email
- JWT sessions + 6-digit login codes stored in DB (login_tokens table)

## Key files
- app/config.py — @lru_cache on get_settings(); clear with get_settings.cache_clear()
- app/services/auth_service.py — get_current_user dependency + login code logic + request_login_code + authenticate
- app/services/email.py — send_login_code via AWS SES (get_settings() inside function)
- app/services/transactions.py — business logic for transactions (balance update, block_negative_balance)
- app/services/user_settings_service.py — get/update user settings
- tests/conftest.py — SQLite in-memory, table truncation per test, client fixture
- docs/ta-liso-BDD.md — canonical BDD scenarios, keep in sync with business rules

## Gotchas
- pydantic-settings: system env vars take priority over .env file
- @lru_cache persists across uvicorn --reload (hot reload), requires full restart or get_settings.cache_clear()
- SQLAlchemy async: no lazy loading; use explicit select() for relationships
- from __future__ import annotations required in all model files (circular refs)
- scalars().all() returns Sequence, not list — wrap with list() when return type is list[T]
- When patching with unittest.mock, patch where the name is looked up (e.g. app.services.email.send_login_code, not app.services.auth_service.send_login_code)

## Cursor Cloud specific instructions

### Services

| Service | How to start | Notes |
|---------|-------------|-------|
| PostgreSQL 16 | `sudo docker compose up -d db` | Runs on port 5432. Credentials: `postgres/postgres`, DB: `taliso` |
| FastAPI dev server | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` | Requires `.env` file and running PostgreSQL |

### Environment setup

- A `.env` file is required at the repo root. See `.env.example` for reference. Required keys: `DATABASE_URL`, `JWT_SECRET_KEY`, `SES_FROM_EMAIL`, `API_KEY`.
- `python-dotenv` is imported by `app/config.py` but is **not** listed in `requirements.txt`. Install it alongside: `pip install -r requirements.txt python-dotenv`.
- `AWS_SECRETS_NAME` must be empty or unset for local dev (skips AWS Secrets Manager lookup).

### Running tests

- `python3 -m pytest tests/ -v` — tests use in-memory SQLite (aiosqlite), no PostgreSQL needed.
- 6 chat router tests (`tests/api/test_chat_router.py`) fail due to a pre-existing bug: they patch `app.services.chat_service.AsyncOpenAI` but `AsyncOpenAI` is imported in `app.services.ai_service`, not `chat_service`. This is not an environment issue.

### Running migrations

- `alembic upgrade head` — uses psycopg2 (sync) against the same PostgreSQL. Must run before starting the dev server.

### Docker daemon

- In Cursor Cloud VMs (nested Docker), start the daemon with: `sudo dockerd &>/tmp/dockerd.log &`
- Docker is configured with `fuse-overlayfs` storage driver and `iptables-legacy` for compatibility.

### API authentication for manual testing

- Auth flow requires AWS SES (not available locally). To authenticate manually:
  1. Call `POST /api/auth/request-code` (will create user + code in DB, but fail on email send)
  2. Read the code from the DB: `sudo docker exec workspace-db-1 psql -U postgres -d taliso -c "SELECT token FROM login_tokens ORDER BY expires_at DESC LIMIT 1;"`
  3. Call `POST /api/auth/verify-code` with the code to get a JWT
- All API endpoints require `X-API-Key` header (value from `API_KEY` env var).
