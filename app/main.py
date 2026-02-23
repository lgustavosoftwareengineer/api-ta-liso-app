from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.dependencies import verify_api_key
from app.routers import auth, categories, chat, transactions, user_settings, users

settings = get_settings()

app = FastAPI(
    title="Tá Liso API",
    version="1.0.0",
    debug=settings.debug,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_api_deps = [Depends(verify_api_key)]

app.include_router(auth.router,              prefix="/api/auth",         dependencies=_api_deps)
app.include_router(categories.router,        prefix="/api/categories",   dependencies=_api_deps)
app.include_router(transactions.router,      prefix="/api/transactions", dependencies=_api_deps)
app.include_router(chat.router,              prefix="/api/chat",         dependencies=_api_deps)
app.include_router(user_settings.router,     prefix="/api/settings",     dependencies=_api_deps)
app.include_router(users.router,             prefix="/api/users/me",     dependencies=_api_deps)


@app.get("/health")
async def health():
    return {"status": "ok"}
