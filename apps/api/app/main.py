"""Al-Mu'allim billing API. Run: uvicorn app.main:app --host 0.0.0.0 --port 8000
with cwd=apps/api after applying apps/api/schema.sql to PostgreSQL.

No payments are activated until the operator adds verified store offerings,
Stripe price IDs, webhook signing secrets, and OIDC authentication.
"""
from contextlib import asynccontextmanager
import os

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.routers.billing import router as billing_router
from app.routers.billing_webhooks import router as webhook_router
from app.routers.verse import router as verse_router
from app.routers.quran import router as quran_router
from app.routers.learning import router as learning_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The Qur'an itself must remain readable even when billing is offline.
    # DB/Redis outages disable only personalised learning and AI billing.
    app.state.quran_reader_cache = {}
    app.state.pg = None
    app.state.redis = None
    dsn = os.environ.get("DATABASE_URL")
    redis_url = os.environ.get("REDIS_URL")
    if dsn:
        try:
            app.state.pg = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=10)
        except (asyncpg.PostgresError, OSError):
            app.state.pg = None
    if redis_url:
        try:
            app.state.redis = Redis.from_url(redis_url, decode_responses=True)
            await app.state.redis.ping()
        except Exception:
            app.state.redis = None
    try:
        yield
    finally:
        if app.state.redis is not None:
            await app.state.redis.aclose()
        if app.state.pg is not None:
            await app.state.pg.close()


app = FastAPI(
    title="Al-Mu'allim Billing and Entitlements",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if os.environ.get("APP_ENV") == "production" else "/docs",
)

origins = [x.strip() for x in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, allow_credentials=False,
    allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"],
)
app.include_router(billing_router)
app.include_router(webhook_router)
app.include_router(verse_router)
app.include_router(quran_router)
app.include_router(learning_router)


@app.get("/health")
async def health():
    return {"ok": True}
