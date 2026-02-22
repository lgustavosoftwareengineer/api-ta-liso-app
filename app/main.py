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
