# 🐍 Tá Liso App — API (Backend)

> **Stack:** FastAPI · SQLAlchemy 2.0 async · PostgreSQL 16 · Redis · Gunicorn + Uvicorn  
> **Servidor:** Gunicorn gerenciando workers Uvicorn, rodando no EC2

---

## 1. Pré-requisitos

| Ferramenta | Versão mínima | Como instalar |
|---|---|---|
| Python | 3.11+ | pyenv ou python.org |
| pip | última | vem com o Python |
| Docker | 24+ (opcional, dev local) | docs.docker.com |
| Git | 2.40+ | git-scm.com |

---

## 2. Setup do Projeto

### 2.1 Criar diretório e Git

```bash
mkdir ta-liso-backend && cd ta-liso-backend
git init
echo ".venv/"        >> .gitignore
echo ".env"          >> .gitignore
echo "__pycache__/"  >> .gitignore
```

### 2.2 Ambiente virtual

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Confirmar
which python   # → .venv/bin/python
```

### 2.3 Estrutura de pastas

```
ta-liso-backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # entrypoint FastAPI
│   ├── config.py            # settings via pydantic-settings
│   ├── database.py          # engine SQLAlchemy + sessão async
│   ├── models/              # modelos SQLAlchemy (tabelas)
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── category.py
│   │   └── transaction.py
│   ├── schemas/             # Pydantic v2 (request / response)
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── category.py
│   │   └── transaction.py
│   ├── routers/             # rotas FastAPI
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── categories.py
│   │   └── transactions.py
│   └── services/            # lógica de negócio
│       ├── __init__.py
│       ├── auth.py
│       ├── email.py          # envio via AWS SES
│       └── categories.py
├── alembic/                 # migrations
├── tests/
├── .env                     # variáveis locais (NÃO commitar)
├── .env.example             # template de variáveis
├── alembic.ini
└── requirements.txt
```

---

## 3. Bibliotecas

### 3.1 Instalação

```bash
pip install \
  fastapi==0.115.0 \
  uvicorn[standard]==0.30.0 \
  gunicorn==23.0.0 \
  sqlalchemy==2.0.36 \
  alembic==1.13.3 \
  asyncpg==0.29.0 \
  psycopg2-binary==2.9.9 \
  pydantic==2.9.0 \
  pydantic-settings==2.5.0 \
  redis==5.1.0 \
  boto3==1.35.0 \
  python-jose[cryptography]==3.3.0 \
  python-multipart==0.0.9 \
  httpx==0.27.0 \
  pytest==8.3.0 \
  pytest-asyncio==0.24.0

pip freeze > requirements.txt
```

### 3.2 Para que serve cada uma

| Biblioteca | Função |
|---|---|
| `fastapi` | Framework web — rotas, validação automática, OpenAPI |
| `uvicorn + gunicorn` | Servidor ASGI — gunicorn gerencia workers uvicorn |
| `sqlalchemy 2.0` | ORM async — queries ao PostgreSQL com type hints |
| `alembic` | Migrations — controle de versão do schema do banco |
| `asyncpg` | Driver async PostgreSQL — usado pelo SQLAlchemy |
| `psycopg2-binary` | Driver sync PostgreSQL — usado pelo Alembic |
| `pydantic v2` | Validação de dados — schemas de request e response |
| `pydantic-settings` | Configuração — carrega `.env` e valida variáveis |
| `redis` | Cache — tokens de login com TTL (Redis local no EC2) |
| `boto3` | AWS SDK — integração com SES e outros serviços |
| `python-jose` | JWT — geração e validação de tokens de sessão |
| `python-multipart` | Suporte a formulários e uploads |
| `httpx` | HTTP client async — usado nos testes de integração |
| `pytest + pytest-asyncio` | Testes com suporte a código async |

---

## 4. Configuração

### 4.1 `.env` (desenvolvimento local)

```env
# Banco de dados
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/taliso

# Redis local
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=troque-para-uma-chave-longa-e-aleatoria
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080

# Token de login (6 dígitos via e-mail)
LOGIN_TOKEN_TTL_SECONDS=600

# AWS SES
AWS_REGION=sa-east-1
SES_FROM_EMAIL=noreply@seudominio.com.br

# App
ENVIRONMENT=development
DEBUG=true
ALLOWED_ORIGINS=http://localhost:5173
```

> **⚠️ Importante:** nunca suba o `.env` para o Git. Use `.env.example` como template com os nomes das variáveis sem valores.

### 4.2 `app/config.py`

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080
    login_token_ttl_seconds: int = 600
    aws_region: str = "sa-east-1"
    ses_from_email: str
    environment: str = "development"
    debug: bool = False
    allowed_origins: list[str] = []

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 4.3 `app/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import auth, categories, transactions

settings = get_settings()

app = FastAPI(title="Tá Liso API", version="1.0.0", debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,         prefix="/api/auth")
app.include_router(categories.router,   prefix="/api/categories")
app.include_router(transactions.router, prefix="/api/transactions")

@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## 5. Banco de Dados e Migrations

### 5.1 Inicializar Alembic

```bash
alembic init alembic
```

Em `alembic/env.py`, configure:
```python
from app.models import Base
from app.config import get_settings

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

### 5.2 Workflow de migrations

```bash
# 1. Altere um model em app/models/

# 2. Gerar migration automática
alembic revision --autogenerate -m "descricao_da_mudanca"

# 3. Revisar o arquivo gerado em alembic/versions/

# 4. Aplicar
alembic upgrade head

# Outros comandos úteis
alembic history --verbose   # ver histórico completo
alembic downgrade -1        # reverter última migration
alembic current             # ver versão aplicada atualmente
```

> **⚠️ Atenção no deploy:** sempre rode `alembic upgrade head` no servidor **antes** de reiniciar a aplicação quando houver mudanças de schema.

---

## 6. Ambiente Local com Docker Compose

```yaml
# docker-compose.yml
version: "3.9"
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: taliso
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports: ["5432:5432"]
    volumes: [pg_data:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

volumes:
  pg_data:
```

```bash
# Subir banco e redis
docker compose up -d

# Rodar migrations
alembic upgrade head

# Iniciar API com hot reload
uvicorn app.main:app --reload --port 8000

# Acessar documentação Swagger
open http://localhost:8000/docs
```

---

## 7. Checklist da Aplicação

- [ ] `.env` criado com todas as variáveis necessárias
- [ ] `alembic upgrade head` executado com sucesso
- [ ] `GET /health` retornando `{"status": "ok"}`
- [ ] Swagger acessível em `/docs`
- [ ] Redis respondendo (`redis-cli ping` → `PONG`)
- [ ] SES configurado e fora do sandbox (modo produção)
- [ ] Testes passando (`pytest`)

---

*Documentação da API — Tá Liso App.*
