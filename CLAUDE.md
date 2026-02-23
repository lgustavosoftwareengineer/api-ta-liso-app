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
