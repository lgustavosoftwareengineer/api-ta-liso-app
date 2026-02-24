"""
Configuração global dos testes. SQLite em memória (cache=shared) para
todas as conexões verem o mesmo DB, sem criar arquivo em disco.
Cada teste começa com tabelas vazias (o código em produção faz commit).
"""
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Definir env antes de importar app (para get_settings em jwt_service etc.)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-at-least-32-characters-long")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "10080")
os.environ.setdefault("LOGIN_TOKEN_TTL_SECONDS", "600")
os.environ.setdefault("SES_FROM_EMAIL", "test@example.com")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("API_KEY", "test-api-key")

from app.database import Base
from app import models  # noqa: F401 - registra todos os modelos no Base
from app.main import app
from app.database import get_db

# SQLite em memória compartilhada: nenhum arquivo em disco
TEST_DATABASE_URL = "sqlite+aiosqlite:///file:testmem?mode=memory&cache=shared"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine, expire_on_commit=False, autoflush=False
)

_tables_created = False

# Ordem: tabelas que referenciam outras primeiro (FK), depois users
_TABLES_TO_TRUNCATE = [
    "login_tokens",
    "user_settings",
    "category_monthly_snapshots",
    "chat_messages",
    "transactions",
    "categories",
    "users",
]


async def ensure_tables():
    global _tables_created
    if not _tables_created:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _tables_created = True


async def truncate_all_tables():
    """Remove todos os dados das tabelas para isolar cada teste (ordem respeita FKs)."""
    async with test_engine.begin() as conn:
        for table in _TABLES_TO_TRUNCATE:
            await conn.execute(text(f"DELETE FROM {table}"))


@pytest_asyncio.fixture
async def db_session():
    """Sessão async por teste; tabelas limpas no início (código em produção faz commit)."""
    await ensure_tables()
    await truncate_all_tables()
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    """Client HTTP async; get_db injeta a mesma db_session do teste."""
    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-API-Key": "test-api-key"},
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
