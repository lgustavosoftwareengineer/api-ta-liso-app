# Tá Liso — API

Backend for the Tá Liso personal finance app. Handles passwordless email authentication, category and transaction management, and natural-language expense registration via an LLM-powered chat endpoint.

## Stack

| Layer            | Technology                             |
| ---------------- | -------------------------------------- |
| Framework        | FastAPI 0.115                          |
| ORM              | SQLAlchemy 2.0 async                   |
| Database (prod)  | PostgreSQL 16 (RDS db.t3.micro)        |
| Database (tests) | SQLite in-memory (aiosqlite)           |
| Cache            | Redis (login tokens)                   |
| Server           | Gunicorn + Uvicorn workers             |
| Migrations       | Alembic                                |
| Auth             | JWT (python-jose) + 6-digit email code |
| Email            | AWS SES / Resend                       |
| LLM              | OpenRouter (via openai SDK)            |
| Infra            | EC2 t4g.micro + Nginx + systemd        |

## Features

- **Passwordless login:** 6-digit code sent by email, 10-minute TTL, stored in the `login_tokens` table
- **JWT session:** 7-day validity; every route requires two headers (`X-API-Key` + `Authorization: Bearer <jwt>`)
- **Categories:** full CRUD with monthly budget (`initial_amount`) and running balance (`current_balance`)
- **Transactions:** debits the category balance on creation; supports configurable negative balance
- **Chat:** natural-language expense registration — the LLM extracts category, description and amount; returns `reply`, `transaction` (when a transaction was created) and `insufficient_balance` (when the category balance is too low). The frontend invalidates and refetches categories and transactions when `transaction` is present so the UI stays in sync.
- **Lazy monthly reset:** instead of a cron job, the system compares `reset_month/reset_year` on each category with the current month and resets the balance on first access of a new month
- **Monthly snapshots:** on reset, creates a `category_monthly_snapshots` record with the budget, total spent and final balance of the closed month
- **User settings:** toggles for low-balance alert, automatic monthly reset and negative-balance blocking

## Project structure

```
app/
├── main.py              # FastAPI app, CORS, routers
├── config.py            # pydantic-settings (@lru_cache)
├── database.py          # SQLAlchemy async engine
├── dependencies.py      # verify_api_key, get_current_user
├── exceptions.py        # HTTPException helpers
├── helpers/             # internal utilities
├── models/              # User, Category, Transaction, LoginToken, UserSettings, Snapshot
├── schemas/             # Pydantic v2 (request / response)
├── routers/             # thin controllers: auth, categories, transactions, chat, users, user_settings
└── services/            # business logic: auth, email, transactions, user_settings, chat
alembic/                 # migrations
tests/
├── conftest.py          # SQLite in-memory fixtures
├── api/                 # integration tests per router
└── unit/                # unit tests for services
```

## Prerequisites

- Python 3.11+
- Docker (for local PostgreSQL and Redis)

## Local setup

### 1. Virtual environment

```bash
python -m venv .venv
source .venv/bin/activate     # Linux / macOS
.venv\Scripts\Activate.ps1    # Windows PowerShell
pip install -r requirements.txt
```

### 2. Environment variables

Create a `.env` file at the project root (never commit this file):

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/taliso
REDIS_URL=redis://localhost:6379/0

JWT_SECRET_KEY=replace-with-a-long-random-secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080

LOGIN_TOKEN_TTL_SECONDS=600

AWS_REGION=sa-east-1
SES_FROM_EMAIL=noreply@yourdomain.com

API_KEY=your-api-key-here

OPENROUTER_API_KEY=your-openrouter-key

ENVIRONMENT=development
DEBUG=true
ALLOWED_ORIGINS=http://localhost:5173
```

### 3. Start database and Redis

```bash
docker compose up -d
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Start the API

```bash
uvicorn app.main:app --reload --port 8000
```

Swagger UI is available at `http://localhost:8000/api/docs`.

### Task runner

The project uses [Task](https://taskfile.dev). See `Taskfile.yml` for available targets.

## Endpoints

| Method   | Route                    | Description                                                            |
| -------- | ------------------------ | ---------------------------------------------------------------------- |
| `GET`    | `/health`                | Health check (no auth required)                                        |
| `POST`   | `/api/auth/request-code` | Request a login code by email                                          |
| `POST`   | `/api/auth/verify-code`  | Validate the code and return a JWT                                     |
| `GET`    | `/api/categories`        | List the authenticated user's categories                               |
| `POST`   | `/api/categories`        | Create a category                                                      |
| `PUT`    | `/api/categories/{id}`   | Update a category                                                      |
| `DELETE` | `/api/categories/{id}`   | Delete a category (linked transactions become SET NULL)                |
| `GET`    | `/api/transactions`      | List transactions (filterable by month)                                |
| `POST`   | `/api/transactions`      | Create a transaction and debit the balance                             |
| `PUT`    | `/api/transactions/{id}` | Update a transaction and recalculate the balance                       |
| `DELETE` | `/api/transactions/{id}` | Delete a transaction and restore the balance                           |
| `GET`    | `/api/chat`              | Retrieve the chat message history                                      |
| `POST`   | `/api/chat`              | Send a message; returns `reply`, `transaction`, `insufficient_balance` |
| `GET`    | `/api/users/me`          | Get the authenticated user's profile                                   |
| `PATCH`  | `/api/users/me`          | Update the user's name                                                 |
| `GET`    | `/api/settings`          | Get user settings                                                      |
| `PATCH`  | `/api/settings`          | Update user settings                                                   |

### Authentication

Every `/api/*` route requires the `X-API-Key` header. All routes outside `/api/auth/*` additionally require `Authorization: Bearer <jwt>`.

## Tests

```bash
pytest
pytest --cov=app --cov-report=term-missing   # with coverage
```

Tests use SQLite in-memory — no external database required.

## Deployment

**Infrastructure:** EC2 t4g.micro (ARM, Free Tier) + RDS db.t3.micro PostgreSQL 16 + local Redis on the EC2 instance.

**CI/CD:** GitHub Actions SSHes into the EC2 instance, runs `git pull`, `pip install`, `alembic upgrade head` and restarts the `taliso` systemd service.

See `docs/ta-liso-INFRA.md` for the full AWS provisioning guide (EC2, RDS, SES, Nginx, Certbot, Route 53).
